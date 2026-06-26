import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PROJECT_ROOT / "document_templates" / "russian_library" / "manifest.json"


def load_template_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []

    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def find_template_by_id(template_id: str) -> dict | None:
    template_id = (template_id or "").strip()

    if not template_id:
        return None

    for item in load_template_manifest():
        if item.get("id") == template_id:
            return item

    return None


def search_templates(
    query: str,
    family: str | None = None,
    limit: int = 8,
) -> list[dict]:
    query = (query or "").strip()
    query_words = tokenize(query)
    manifest = load_template_manifest()

    scored = []

    for item in manifest:
        if family and family != "unknown" and item.get("family") != family:
            continue

        score = score_template(item, query_words)

        if score <= 0:
            continue

        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [item for _, item in scored[:limit]]


def choose_best_template(
    query: str,
    family: str | None = None,
) -> dict | None:
    results = search_templates(query=query, family=family, limit=1)

    return results[0] if results else None


def score_template(item: dict, query_words: list[str]) -> int:
    text = " ".join([
        item.get("title") or "",
        item.get("category") or "",
        item.get("subcategory") or "",
        item.get("source_path") or "",
        item.get("family") or "",
    ]).lower()

    score = 0

    for word in query_words:
        if word in text:
            score += 3

    title = (item.get("title") or "").lower()

    if "взыск" in title:
        score += 2

    if "задолж" in title or "долг" in title:
        score += 2

    if "договор" in title:
        score += 1

    if "с представителем" in title:
        score -= 1

    return score


def tokenize(value: str) -> list[str]:
    value = value.lower()
    words = re.findall(r"[a-zа-яё0-9]{3,}", value, flags=re.UNICODE)

    return words[:30]