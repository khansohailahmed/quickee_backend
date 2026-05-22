import hashlib
import uuid
from datetime import datetime
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import Distance, FieldCondition, Filter, PointStruct, VectorParams

from config.settings import get_settings


def _make_point_id(key: str) -> str:
    """Convert any string key to a valid Qdrant UUID point-id.

    Qdrant accepts point IDs that are either unsigned integers or UUID strings.
    MD5 returns 32 hex chars which is exactly the format UUID needs.
    """
    raw_hex = hashlib.md5(key.encode()).hexdigest()  # 32-char hex string
    return str(uuid.UUID(raw_hex))                   # 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'


class QdrantClientWrapper:
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[QdrantClient] = None

    def connect(self):
        if self.client is None:
            self.client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port,
            )
        return self.client

    # ------------------------------------------------------------------
    # Collection setup
    # ------------------------------------------------------------------

    def create_clothing_collection(self, force_recreate: bool = False):
        client = self.connect()
        name = self.settings.qdrant_collection_name

        try:
            if client.collection_exists(name):
                if force_recreate:
                    client.delete_collection(name)
                    print(f"Deleted existing collection: {name}")
                else:
                    print(f"Collection '{name}' already exists – skipping creation.")
                    return

            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.settings.embedding_dim,   # 384 (all-MiniLM-L6-v2)
                    distance=Distance.COSINE,
                ),
            )
            print(f"Created collection: {name}")

            # Payload indexes for fast metadata filtering
            for field, schema in [
                ("category", "keyword"),
                ("brand", "keyword"),
                ("color", "keyword"),
                ("price_inr", "float"),          # numeric index for Range filters
            ]:
                client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=schema,
                )
            print(f"Created payload indexes for {name}")

        except ResponseHandlingException as e:
            print(f"Error creating collection: {e}")
            raise

    def create_cache_collection(self, force_recreate: bool = False):
        client = self.connect()
        name = self.settings.qdrant_cache_collection_name

        try:
            if client.collection_exists(name):
                if force_recreate:
                    client.delete_collection(name)
                else:
                    print(f"Cache collection '{name}' already exists – skipping.")
                    return

            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Created cache collection: {name}")

        except ResponseHandlingException as e:
            print(f"Error creating cache collection: {e}")
            raise

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_items(
        self,
        collection_name: str,
        items: list[dict],
        vectors: list[list[float]],
    ):
        client = self.connect()

        points = [
            PointStruct(
                id=_make_point_id(str(item.get("item_id", idx))),
                vector=vector,
                payload=item,
            )
            for idx, (item, vector) in enumerate(zip(items, vectors))
        ]

        client.upsert(collection_name=collection_name, points=points)
        print(f"Upserted {len(points)} items to '{collection_name}'")

    def cache_query(
        self,
        query_vector: list[float],
        original_query: str,
        response_json: str,
    ) -> str:
        payload = {
            "original_query": original_query,
            "response_json": response_json,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.upsert_items(
            collection_name=self.settings.qdrant_cache_collection_name,
            items=[payload],
            vectors=[query_vector],
        )
        return _make_point_id(original_query)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        query_filter: Optional[Filter] = None,
        score_threshold: Optional[float] = None,
    ) -> list[dict]:
        client = self.connect()
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [
            {"id": hit.id, "score": hit.score, "payload": hit.payload}
            for hit in results
        ]

    def search_groups(
        self,
        collection_name: str,
        query_vector: list[float],
        group_by: str,
        limit: int = 3,
        groups_count: int = 3,
    ) -> list[dict]:
        client = self.connect()
        results = client.search_groups(
            collection_name=collection_name,
            query_vector=query_vector,
            group_by=group_by,
            limit=limit,
            groups_count=groups_count,
        )
        return [
            {
                "group_id": group.id,
                "hits": [
                    {"id": h.id, "score": h.score, "payload": h.payload}
                    for h in group.hits
                ],
            }
            for group in results.groups
        ]

    def get_collection_info(self, collection_name: str) -> dict:
        client = self.connect()
        try:
            info = client.get_collection(collection_name)
            return {
                "name": info.config.params.vectors.size
                if hasattr(info.config.params.vectors, "size")
                else "multi",
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": str(info.status),
            }
        except Exception as e:
            return {"error": str(e)}


qdrant_client = QdrantClientWrapper()


def get_qdrant_client() -> QdrantClientWrapper:
    return qdrant_client
