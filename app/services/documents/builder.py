from app.services.interviews.engine import start_or_update_interview
from app.services.interviews.preview import build_document_preview
from app.services.documents.docx_template_renderer import get_docx_template_info


def build_document_from_request(
    user_request: str,
    client_context: str = "",
    previous_data: dict | None = None,
    answers: dict | None = None,
    forced_family: str | None = None,
) -> dict:
    user_request = (user_request or "").strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    result = start_or_update_interview(
        user_request=user_request,
        client_context=client_context,
        previous_data=previous_data,
        answers=answers,
        forced_family=forced_family,
    )

    draft = build_document_preview(result)
    family = result["family"]

    return {
        "status": "ok",
        "detected_family": family,
        "detected_label": result["label"],
        "detected_document_type": result["interview"].get("template") or "",
        "detected_confidence": result.get("confidence", 0),
        "interview": {
            "family": family,
            "label": result["label"],
            "template": result["interview"].get("template") or "",
        },
        "extracted_data": result["data"],
        "visible_fields": result["visible_fields"],
        "missing_required_fields": result["missing_required_fields"],
        "completeness": result["completeness"],
        "draft": draft,
        "sources": _build_sources(result),
        "docx_template": get_docx_template_info(family),
    }


def _build_sources(interview_result: dict) -> list[dict]:
    interview = interview_result.get("interview") or {}
    sources = []

    template = interview.get("template") or ""
    template_path = interview.get("template_path") or ""

    if template:
        sources.append({
            "title": f"Word-шаблон: {template}",
            "document_type": "docx_template",
            "source_url": template_path,
        })

    sources.append({
        "title": f"Interview-сценарий: {interview.get('label') or 'Юридический документ'}",
        "document_type": "interview_scenario",
        "source_url": interview.get("source") or "",
    })

    return sources[:5]