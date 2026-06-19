from app.providers.llm.openai import generate_document_draft
from app.services.knowledge.search import (
    search_knowledge,
    search_knowledge_by_phrase,
    build_knowledge_context,
)


DOCUMENT_TYPES = {
    "claim": {
        "document_type": "claim_generic",
        "keywords": ["претенз", "досудебн"],
    },
    "lawsuit": {
        "document_type": "lawsuit_generic",
        "keywords": ["иск", "исков"],
    },
    "motion": {
        "document_type": "motion_generic",
        "keywords": ["ходатайств"],
    },
    "response": {
        "document_type": "response_generic",
        "keywords": ["отзыв", "возражен"],
    },
    "appeal": {
        "document_type": "appeal_generic",
        "keywords": ["апелляц"],
    },
    "cassation": {
        "document_type": "cassation_generic",
        "keywords": ["кассац"],
    },
    "complaint": {
        "document_type": "complaint_generic",
        "keywords": ["жалоб"],
    },
}


def detect_document_family(user_request: str) -> dict:
    text = user_request.lower()

    for family, config in DOCUMENT_TYPES.items():
        for keyword in config["keywords"]:
            if keyword in text:
                return {
                    "family": family,
                    "document_type": config["document_type"],
                }

    return {
        "family": "unknown",
        "document_type": "",
    }


def build_document_from_request(user_request: str) -> dict:
    user_request = user_request.strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    detected = detect_document_family(user_request)
    family = detected["family"]
    document_type = detected["document_type"]

    targeted_results = []

    if document_type:
        targeted_results.extend(
            search_knowledge_by_phrase(f"DOCUMENT_TYPE: {document_type}", limit=6)
        )

    if family != "unknown":
        targeted_results.extend(
            search_knowledge_by_phrase(f"DOCUMENT_FAMILY: {family}", limit=6)
        )

    general_results = search_knowledge(user_request, limit=8)

    knowledge_results = _deduplicate_results(targeted_results + general_results)
    knowledge_context = build_knowledge_context(knowledge_results)

    draft = generate_document_draft(
        user_request=user_request,
        knowledge_context=knowledge_context,
        detected_family=family,
        detected_document_type=document_type,
    )

    return {
        "status": "ok",
        "detected_family": family,
        "detected_document_type": document_type,
        "draft": draft,
        "sources": [
            {
                "title": item["title"],
                "document_type": item["document_type"],
                "source_url": item["source_url"],
            }
            for item in knowledge_results
        ],
    }


def _deduplicate_results(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []

    for item in results:
        key = item.get("chunk_id")

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique