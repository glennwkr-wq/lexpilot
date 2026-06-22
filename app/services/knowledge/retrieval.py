from app.services.knowledge.search import (
    search_knowledge,
    search_knowledge_by_phrase,
)


DOCUMENT_CONFIG = {
    "claim": {
        "template_type": "claim_generic",
        "intake_type": "claim_generic",
        "template_path": "02_document_templates/verified/claims/claim_generic.md",
        "intake_path": "12_intake_forms/claim_intake_form.md",
    },
    "lawsuit": {
        "template_type": "lawsuit_generic",
        "intake_type": "lawsuit_generic",
        "template_path": "02_document_templates/verified/lawsuits/lawsuit_generic.md",
        "intake_path": "12_intake_forms/lawsuit_intake_form.md",
    },
    "motion": {
        "template_type": "motion_generic",
        "intake_type": "motion_generic",
        "template_path": "02_document_templates/verified/motions/motion_generic.md",
        "intake_path": "12_intake_forms/motion_intake_form.md",
    },
    "response": {
        "template_type": "response_generic",
        "intake_type": "response_generic",
        "template_path": "02_document_templates/verified/responses/response_generic.md",
        "intake_path": "12_intake_forms/response_intake_form.md",
    },
    "appeal": {
        "template_type": "appeal_generic",
        "intake_type": "appeal_generic",
        "template_path": "02_document_templates/verified/appeals/appeal_generic.md",
        "intake_path": "12_intake_forms/appeal_intake_form.md",
    },
    "cassation": {
        "template_type": "cassation_generic",
        "intake_type": "cassation_generic",
        "template_path": "02_document_templates/verified/cassations/cassation_generic.md",
        "intake_path": "12_intake_forms/cassation_intake_form.md",
    },
    "complaint": {
        "template_type": "complaint_generic",
        "intake_type": "complaint_generic",
        "template_path": "02_document_templates/verified/complaints/complaint_generic.md",
        "intake_path": "12_intake_forms/complaint_intake_form.md",
    },
}


def build_retrieval_pack(
    family: str,
    user_request: str,
) -> dict:
    config = DOCUMENT_CONFIG.get(family)

    if not config:
        return {
            "template": None,
            "intake_form": None,
            "supporting_materials": search_knowledge(user_request, limit=5),
        }

    template = _find_first_by_path(config["template_path"])
    intake_form = _find_first_by_path(config["intake_path"])

    supporting_materials = search_knowledge(user_request, limit=5)

    supporting_materials = _exclude_sources(
        supporting_materials,
        excluded_source_urls=[
            config["template_path"],
            config["intake_path"],
        ],
    )

    return {
        "template": template,
        "intake_form": intake_form,
        "supporting_materials": supporting_materials,
    }


def build_retrieval_context(retrieval_pack: dict) -> str:
    blocks = []

    template = retrieval_pack.get("template")
    intake_form = retrieval_pack.get("intake_form")
    supporting_materials = retrieval_pack.get("supporting_materials") or []

    if template:
        blocks.append(_format_block("ОСНОВНОЙ ШАБЛОН ДОКУМЕНТА", template))

    if intake_form:
        blocks.append(_format_block("INTAKE FORM / ОБЯЗАТЕЛЬНЫЕ ДАННЫЕ", intake_form))

    for index, item in enumerate(supporting_materials, start=1):
        blocks.append(_format_block(f"ДОПОЛНИТЕЛЬНЫЙ МАТЕРИАЛ {index}", item))

    return "\n\n---\n\n".join(blocks)


def _find_first_by_path(source_url_part: str) -> dict | None:
    results = search_knowledge_by_phrase(source_url_part, limit=1)
    return results[0] if results else None


def _exclude_sources(
    results: list[dict],
    excluded_source_urls: list[str],
) -> list[dict]:
    cleaned = []

    for item in results:
        source_url = item.get("source_url") or ""

        if any(excluded in source_url for excluded in excluded_source_urls):
            continue

        cleaned.append(item)

    return cleaned


def _format_block(label: str, item: dict) -> str:
    return f"""
[{label}]
Название: {item.get("title")}
Тип: {item.get("document_type")}
Путь: {item.get("source_url")}

Содержимое:
{item.get("content")}
""".strip()