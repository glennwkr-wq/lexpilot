from app.providers.llm.openai import generate_document_draft
from app.services.knowledge.retrieval import (
    build_retrieval_pack,
    build_retrieval_context,
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


def build_document_from_request(
    user_request: str,
    client_context: str = "",
) -> dict:
    user_request = user_request.strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    detected = detect_document_family(user_request)
    family = detected["family"]
    document_type = detected["document_type"]

    retrieval_pack = build_retrieval_pack(
        family=family,
        user_request=user_request,
    )
    knowledge_context = build_retrieval_context(retrieval_pack)

    draft = generate_document_draft(
        user_request=user_request,
        knowledge_context=knowledge_context,
        detected_family=family,
        detected_document_type=document_type,
        client_context=client_context,
    )

    return {
        "status": "ok",
        "detected_family": family,
        "detected_document_type": document_type,
        "draft": draft,
        "sources": _build_sources(retrieval_pack),
    }


def _build_sources(retrieval_pack: dict) -> list[dict]:
    items = []

    template = retrieval_pack.get("template")
    intake_form = retrieval_pack.get("intake_form")
    supporting_materials = retrieval_pack.get("supporting_materials") or []

    if template:
        items.append(template)

    if intake_form:
        items.append(intake_form)

    items.extend(supporting_materials)

    return [
        {
            "title": item["title"],
            "document_type": item["document_type"],
            "source_url": item["source_url"],
        }
        for item in items
    ]