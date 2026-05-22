from typing import TypedDict

from openai import OpenAI

from agent.prompts.system_prompts import STYLIST_NOTE_SYSTEM, STYLIST_NOTE_USER
from config.settings import get_settings


class StylistNoteOutput(TypedDict):
    stylist_note: str
    tokens_used: int


class StylistNoteGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(
            base_url=self.settings.ollama_base_url,
            api_key=self.settings.ollama_api_key,
        )

    def generate(
        self,
        selected_items: list[dict],
        occasion: str,
        season: str,
    ) -> StylistNoteOutput:
        # Flatten nested payload if items come from Qdrant hit dicts
        def _get(item: dict, key: str, default: str = "N/A") -> str:
            payload = item.get("payload", item)
            return str(payload.get(key, default))

        outfit_summary = ", ".join(
            f"{_get(item, 'name')} ({_get(item, 'color')}, {_get(item, 'brand')})"
            for item in selected_items
        )

        user_prompt = STYLIST_NOTE_USER.format(
            outfit_summary=outfit_summary or "curated outfit",
            occasion=occasion or "casual",
            season=season or "all season",
        )

        response = self.client.chat.completions.create(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": STYLIST_NOTE_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=180,   # slightly generous for local model verbosity
            temperature=0.7,  # some creativity for the stylist voice
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return StylistNoteOutput(
            stylist_note=content.strip(),
            tokens_used=tokens_used,
        )


def stylist_note_node(state: dict) -> dict:
    generator = StylistNoteGenerator()
    result = generator.generate(
        selected_items=state.get("selected_items", []),
        occasion=state.get("occasion"),
        season=state.get("season"),
    )
    return {
        **state,
        "stylist_note": result["stylist_note"],
        "tokens_used": state.get("tokens_used", 0) + result["tokens_used"],
    }
