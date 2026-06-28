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
        item_family = item.get("family") or ""

        if family and family not in ["unknown", "document"]:
            if item_family != family:
                continue

        score = score_template(item, query_words, family)

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


def score_template(item: dict, query_words: list[str], family: str | None = None) -> int:
    title = (item.get("title") or "").lower()
    category = (item.get("category") or "").lower()
    subcategory = (item.get("subcategory") or "").lower()
    source_path = (item.get("source_path") or "").lower()
    item_family = (item.get("family") or "").lower()

    text = " ".join([title, category, subcategory, source_path, item_family])

    score = 0

    for word in query_words:
        if word in title:
            score += 6
        elif word in subcategory:
            score += 4
        elif word in category:
            score += 3
        elif word in source_path:
            score += 2
        elif word in text:
            score += 1

    query_text = " ".join(query_words)

    if family == "motion":
        if "ходатай" in title or "ходатай" in source_path:
            score += 40
        if "иск" in title and "ходатай" not in title:
            score -= 20

    if family == "claim":
        if "претенз" in title or "претенз" in source_path:
            score += 30
        if "иск" in title:
            score -= 10

    if family == "complaint":
        if "жалоб" in title or "жалоб" in source_path:
            score += 30

    if family == "lawsuit":
        if "иск" in title or "исков" in title:
            score += 25
        if "претенз" in title:
            score -= 10

    if family == "contract":
        if "договор" in title or "договор" in source_path:
            score += 25

    if "взыск" in query_text and "взыск" in title:
        score += 8

    if ("задолж" in query_text or "долг" in query_text) and ("задолж" in title or "долг" in title):
        score += 8

    if "постав" in query_text and "постав" in title:
        score += 8

    if "займ" in query_text and "займ" in title:
        score += 8

    query_mentions_counterclaim = "встречн" in query_text

    if "встречн" in title and not query_mentions_counterclaim:
        score -= 80

    if "встречн" in title and query_mentions_counterclaim:
        score += 30

    if family == "lawsuit":
        if title.startswith("исковое заявление") and "встречн" not in title:
            score += 12

    if "с представителем" in title:
        score -= 2

    return score


def tokenize(value: str) -> list[str]:
    value = value.lower()
    words = re.findall(r"[a-zа-яё0-9]{3,}", value, flags=re.UNICODE)

    return words[:30]