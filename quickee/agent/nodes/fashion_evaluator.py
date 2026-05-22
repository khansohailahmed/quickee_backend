import json
from typing import Optional, TypedDict

from openai import OpenAI

from agent.prompts.system_prompts import FASHION_EVALUATOR_SYSTEM, FASHION_EVALUATOR_USER
from config.settings import get_settings


class FashionEvaluatorOutput(TypedDict):
    selected_items: list[dict]
    evaluation_reasoning: str
    tokens_used: int


class FashionEvaluator:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(
            base_url=self.settings.ollama_base_url,
            api_key=self.settings.ollama_api_key,
        )

    def evaluate_and_select(
        self,
        retrieved_items: dict[str, list[dict]],
        occasion: Optional[str],
        season: Optional[str],
        existing_items: list[str],
    ) -> FashionEvaluatorOutput:
        tops    = retrieved_items.get("tops", [])
        bottoms = retrieved_items.get("bottoms", [])
        shoes   = retrieved_items.get("shoes", [])

        tops_text    = json.dumps([{"id": t["id"], **t["payload"]} for t in tops],    indent=2)
        bottoms_text = json.dumps([{"id": b["id"], **b["payload"]} for b in bottoms], indent=2)
        shoes_text   = json.dumps([{"id": s["id"], **s["payload"]} for s in shoes],   indent=2)

        user_prompt = FASHION_EVALUATOR_USER.format(
            occasion=occasion or "casual",
            season=season or "all season",
            existing_items=", ".join(existing_items) if existing_items else "none",
            tops=tops_text,
            bottoms=bottoms_text,
            shoes=shoes_text,
        )

        response = self.client.chat.completions.create(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": FASHION_EVALUATOR_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.2,
        )

        content = response.choices[0].message.content or "{}"
        tokens_used = response.usage.total_tokens if response.usage else 0

        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            result = json.loads(content)
            selected_items = result.get("selected_items", [])
            reasoning = result.get("reasoning", "")
        except json.JSONDecodeError:
            selected_items = []
            reasoning = "Error parsing evaluation results"

        return FashionEvaluatorOutput(
            selected_items=selected_items,
            evaluation_reasoning=reasoning,
            tokens_used=tokens_used,
        )


def fashion_evaluator_node(state: dict) -> dict:
    evaluator = FashionEvaluator()
    result = evaluator.evaluate_and_select(
        retrieved_items=state.get("retrieved_items", {}),
        occasion=state.get("occasion"),
        season=state.get("season"),
        existing_items=state.get("existing_items", []),
    )
    return {
        **state,
        "selected_items":       result["selected_items"],
        "evaluation_reasoning": result["evaluation_reasoning"],
        "tokens_used": state.get("tokens_used", 0) + result["tokens_used"],
    }
