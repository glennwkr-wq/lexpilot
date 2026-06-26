from io import BytesIO
from pathlib import Path

from docxtpl import DocxTemplate


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DOCX_TEMPLATE_MAP = {
    "claim": PROJECT_ROOT / "document_templates" / "docx" / "claims" / "claim_generic.docx",
    "lawsuit": PROJECT_ROOT / "document_templates" / "docx" / "lawsuits" / "lawsuit_generic.docx",
    "motion": PROJECT_ROOT / "document_templates" / "docx" / "motions" / "motion_generic.docx",
    "complaint": PROJECT_ROOT / "document_templates" / "docx" / "complaints" / "complaint_generic.docx",
    "response": PROJECT_ROOT / "document_templates" / "docx" / "responses" / "response_generic.docx",
    "appeal": PROJECT_ROOT / "document_templates" / "docx" / "appeals" / "appeal_generic.docx",
    "cassation": PROJECT_ROOT / "document_templates" / "docx" / "cassations" / "cassation_generic.docx",
}


def get_docx_template_path(document_family: str | None) -> Path | None:
    if not document_family:
        return None

    template_path = DOCX_TEMPLATE_MAP.get(document_family)

    if not template_path or not template_path.exists():
        return None

    return template_path


def get_docx_template_info(document_family: str | None) -> dict:
    template_path = get_docx_template_path(document_family)

    return {
        "available": bool(template_path),
        "path": str(template_path) if template_path else "",
        "filename": template_path.name if template_path else "",
    }


def render_docx_template(
    document_family: str,
    extracted_data: dict,
    title: str = "Юридический документ",
    client_name: str = "",
) -> BytesIO:
    template_path = get_docx_template_path(document_family)

    if not template_path:
        raise FileNotFoundError("DOCX-шаблон для выбранного типа документа не найден.")

    document = DocxTemplate(str(template_path))
    context = build_docx_context(
        extracted_data=extracted_data,
        title=title,
        client_name=client_name,
    )

    document.render(context)

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    return file_stream


def build_docx_context(
    extracted_data: dict,
    title: str = "Юридический документ",
    client_name: str = "",
) -> dict:
    extracted_data = extracted_data if isinstance(extracted_data, dict) else {}

    fields = extracted_data.get("fields")
    parties = extracted_data.get("parties")
    amounts = extracted_data.get("amounts")
    dates = extracted_data.get("dates")
    risks = extracted_data.get("risks")
    notes = extracted_data.get("notes")

    if not isinstance(fields, dict):
        fields = {}

    if not isinstance(parties, dict):
        parties = {}

    if not isinstance(amounts, list):
        amounts = []

    if not isinstance(dates, list):
        dates = []

    if not isinstance(risks, list):
        risks = []

    if not isinstance(notes, list):
        notes = []

    context = {
        "document_title": title or "Юридический документ",
        "client_name": client_name or "",
        "parties": parties,
        "amounts": amounts,
        "dates": dates,
        "risks": risks,
        "notes": notes,
    }

    for key, value in fields.items():
        context[key] = _normalize_template_value(value)

    for key, value in parties.items():
        context[f"party_{key}"] = _normalize_template_value(value)

    context.setdefault("sender", "[УКАЗАТЬ_ОТПРАВИТЕЛЯ]")
    context.setdefault("recipient", "[УКАЗАТЬ_ПОЛУЧАТЕЛЯ]")
    context.setdefault("claim_basis", "[УКАЗАТЬ_ОСНОВАНИЕ_ТРЕБОВАНИЙ]")
    context.setdefault("demand", "[УКАЗАТЬ_ТРЕБОВАНИЕ]")
    context.setdefault("deadline", "[УКАЗАТЬ_СРОК]")
    context.setdefault("contract_number", "[УКАЗАТЬ_НОМЕР_ДОГОВОРА]")
    context.setdefault("contract_date", "[УКАЗАТЬ_ДАТУ_ДОГОВОРА]")
    context.setdefault("debt_amount", "[УКАЗАТЬ_СУММУ_ДОЛГА]")
    context.setdefault("penalty_amount", "[УКАЗАТЬ_СУММУ_НЕУСТОЙКИ]")
    context.setdefault("evidence", "[УКАЗАТЬ_ДОКАЗАТЕЛЬСТВА]")
    context.setdefault("attachments", "[УКАЗАТЬ_ПРИЛОЖЕНИЯ]")

    context.setdefault("court", "[УКАЗАТЬ_СУД]")
    context.setdefault("plaintiff", "[УКАЗАТЬ_ИСТЦА]")
    context.setdefault("defendant", "[УКАЗАТЬ_ОТВЕТЧИКА]")
    context.setdefault("claims", "[УКАЗАТЬ_ИСКОВЫЕ_ТРЕБОВАНИЯ]")
    context.setdefault("facts", "[УКАЗАТЬ_ОБСТОЯТЕЛЬСТВА]")
    context.setdefault("claim_price", "[УКАЗАТЬ_ЦЕНУ_ИСКА]")
    context.setdefault("state_duty", "[УКАЗАТЬ_ГОСПОШЛИНУ]")
    context.setdefault("pretrial_claim", "[УКАЗАТЬ_ДОСУДЕБНЫЙ_ПОРЯДОК]")

    context.setdefault("court_or_body", "[УКАЗАТЬ_СУД_ИЛИ_ОРГАН]")
    context.setdefault("case_number", "[УКАЗАТЬ_НОМЕР_ДЕЛА]")
    context.setdefault("applicant", "[УКАЗАТЬ_ЗАЯВИТЕЛЯ]")
    context.setdefault("request", "[УКАЗАТЬ_ПРОСЬБУ]")
    context.setdefault("grounds", "[УКАЗАТЬ_ОСНОВАНИЯ]")

    return context


def _normalize_template_value(value) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        if not value:
            return ""

        return "\n".join(str(item) for item in value)

    if isinstance(value, dict):
        if not value:
            return ""

        return "\n".join(f"{key}: {item}" for key, item in value.items())

    return str(value)