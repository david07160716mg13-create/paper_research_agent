"""
Query Parser Agent — Uses OLLAMA to interpret natural-language research queries
and extract structured search parameters.
"""
import json
import requests
from config import OLLAMA_CHAT_ENDPOINT, OLLAMA_MODEL, ANALYSIS_TEMPERATURE

PARSE_SYSTEM_PROMPT = """You are a research query parser. Given a user's natural-language request about finding academic papers, extract the following structured information and return ONLY valid JSON (no markdown, no explanation):

{
  "topic_en": "English search keywords for Semantic Scholar (translate if input is not English)",
  "topic_original": "Original topic as stated by user",
  "count": <number of papers requested, default 10>,
  "filters": {
    "qs_ranking": <maximum QS ranking to filter, null if not specified>,
    "year_from": <earliest publication year, null if not specified>,
    "year_to": <latest publication year, null if not specified>
  }
}

Rules:
- Always translate the topic to English for the search query.
- If the user says "QS排名前100" it means qs_ranking = 100.
- If no count is specified, default to 10.
- Return ONLY the JSON object, nothing else.
"""


def parse_query(user_query: str, model: str = None) -> dict:
    """
    Send the user's natural-language query to OLLAMA and return
    a structured dict with search parameters.
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ],
        "stream": False,
        "options": {"temperature": ANALYSIS_TEMPERATURE},
    }

    try:
        resp = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=120)
        resp.raise_for_status()
        content = resp.json()["message"]["content"].strip()

        # Strip possible markdown fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        parsed = json.loads(content)
        # Ensure required keys exist
        parsed.setdefault("topic_en", "machine learning")
        parsed.setdefault("topic_original", user_query)
        parsed.setdefault("count", 10)
        parsed.setdefault("filters", {})
        parsed["filters"].setdefault("qs_ranking", None)
        parsed["filters"].setdefault("year_from", None)
        parsed["filters"].setdefault("year_to", None)
        return parsed

    except (requests.RequestException, json.JSONDecodeError, KeyError) as exc:
        # Fallback: return a basic structure
        return {
            "topic_en": user_query,
            "topic_original": user_query,
            "count": 10,
            "filters": {
                "qs_ranking": None,
                "year_from": None,
                "year_to": None,
            },
            "_parse_error": str(exc),
        }
