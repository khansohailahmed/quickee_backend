import json
from typing import Optional, TypedDict

from openai import OpenAI

from agent.prompts.system_prompts import PROMPT_PARSER_SYSTEM, PROMPT_PARSER_USER
from config.settings import get_settings


class PromptParserOutput(TypedDict):
    existing_items: list[str]
    occasion: Optional[str]
    desired_categories: list[str]
    color_preferences: list[str]
    max_budget: Optional[float]
    season: Optional[str]
    tokens_used: int


class PromptParser:
    def __init__(self):
        self.settings = get_settings()
        # Ollama exposes an OpenAI-compatible API — no code-path change needed,
        # only the base_url and api_key differ from the cloud version.
        self.client = OpenAI(
            base_url=self.settings.ollama_base_url,
            api_key=self.settings.ollama_api_key,
        )

    def parse(self, query: str) -> PromptParserOutput:
        user_prompt = PROMPT_PARSER_USER.format(query=query)

        response = self.client.chat.completions.create(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": PROMPT_PARSER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            # Ollama supports response_format for models that have JSON mode
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.1,   # low temp → deterministic structured extraction
        )

        content = response.choices[0].message.content or "{}"
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Strip markdown fences that some Ollama models add despite json_object mode
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {}

        return PromptParserOutput(
            existing_items=parsed.get("existing_items", []),
            occasion=parsed.get("occasion"),
            desired_categories=parsed.get("desired_categories", ["tops", "bottoms"]),
            color_preferences=parsed.get("color_preferences", []),
            max_budget=parsed.get("max_budget"),
            season=parsed.get("season"),
            tokens_used=tokens_used,
        )


def prompt_parser_node(state: dict) -> dict:
    parser = PromptParser()
    result = parser.parse(state.get("query", ""))
    return {
        **state,
        **result,
        "tokens_used": state.get("tokens_used", 0) + result["tokens_used"],
    }
