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
    "unknown": PROJECT_ROOT / "document_templates" / "docx" / "claims" / "claim_generic.docx",
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
        "amounts_text": _list_to_text(amounts),
        "dates_text": _list_to_text(dates),
        "risks_text": _list_to_text(risks),
        "notes_text": _list_to_text(notes),
    }

    for key, value in fields.items():
        context[key] = _normalize_template_value(value)

    for key, value in parties.items():
        context[f"party_{key}"] = _normalize_template_value(value)

    defaults = {
        "sender": "[УКАЗАТЬ_ОТПРАВИТЕЛЯ]",
        "recipient": "[УКАЗАТЬ_ПОЛУЧАТЕЛЯ]",
        "claim_basis": "[УКАЗАТЬ_ОСНОВАНИЕ_ТРЕБОВАНИЙ]",
        "demand": "[УКАЗАТЬ_ТРЕБОВАНИЕ]",
        "deadline": "[УКАЗАТЬ_СРОК]",
        "contract_number": "[УКАЗАТЬ_НОМЕР_ДОГОВОРА]",
        "contract_date": "[УКАЗАТЬ_ДАТУ_ДОГОВОРА]",
        "debt_amount": "[УКАЗАТЬ_СУММУ_ДОЛГА]",
        "penalty_amount": "[УКАЗАТЬ_СУММУ_НЕУСТОЙКИ]",
        "evidence": "[УКАЗАТЬ_ДОКАЗАТЕЛЬСТВА]",
        "attachments": "[УКАЗАТЬ_ПРИЛОЖЕНИЯ]",
        "court": "[УКАЗАТЬ_СУД]",
        "plaintiff": "[УКАЗАТЬ_ИСТЦА]",
        "defendant": "[УКАЗАТЬ_ОТВЕТЧИКА]",
        "claims": "[УКАЗАТЬ_ИСКОВЫЕ_ТРЕБОВАНИЯ]",
        "facts": "[УКАЗАТЬ_ОБСТОЯТЕЛЬСТВА]",
        "claim_price": "[УКАЗАТЬ_ЦЕНУ_ИСКА]",
        "state_duty": "[УКАЗАТЬ_ГОСПОШЛИНУ]",
        "pretrial_claim": "[УКАЗАТЬ_ДОСУДЕБНЫЙ_ПОРЯДОК]",
        "court_or_body": "[УКАЗАТЬ_СУД_ИЛИ_ОРГАН]",
        "case_number": "[УКАЗАТЬ_НОМЕР_ДЕЛА]",
        "applicant": "[УКАЗАТЬ_ЗАЯВИТЕЛЯ]",
        "request": "[УКАЗАТЬ_ПРОСЬБУ]",
        "grounds": "[УКАЗАТЬ_ОСНОВАНИЯ]",
        "participants": "[УКАЗАТЬ_УЧАСТНИКОВ]",
        "addressee": "[УКАЗАТЬ_АДРЕСАТА]",
        "authority": "[УКАЗАТЬ_ОРГАН_ИЛИ_ДОЛЖНОСТНОЕ_ЛИЦО]",
        "challenged_action": "[УКАЗАТЬ_ЧТО_ОБЖАЛУЕТСЯ]",
        "decision_date": "[УКАЗАТЬ_ДАТУ_РЕШЕНИЯ_ИЛИ_ДЕЙСТВИЯ]",
        "respondent": "[УКАЗАТЬ_ЛИЦО_ПОДАЮЩЕЕ_ОТЗЫВ]",
        "opponent": "[УКАЗАТЬ_ОППОНЕНТА]",
        "position": "[УКАЗАТЬ_ПОЗИЦИЮ_ПО_ТРЕБОВАНИЯМ]",
        "arguments": "[УКАЗАТЬ_ВОЗРАЖЕНИЯ]",
        "appeal_court": "[УКАЗАТЬ_АПЕЛЛЯЦИОННЫЙ_СУД]",
        "first_instance_court": "[УКАЗАТЬ_СУД_ПЕРВОЙ_ИНСТАНЦИИ]",
        "decision": "[УКАЗАТЬ_ОБЖАЛУЕМЫЙ_СУДЕБНЫЙ_АКТ]",
        "appeal_arguments": "[УКАЗАТЬ_ДОВОДЫ_АПЕЛЛЯЦИИ]",
        "requested_result": "[УКАЗАТЬ_ПРОСИТЕЛЬНУЮ_ЧАСТЬ]",
        "cassation_court": "[УКАЗАТЬ_КАССАЦИОННЫЙ_СУД]",
        "challenged_acts": "[УКАЗАТЬ_ОБЖАЛУЕМЫЕ_СУДЕБНЫЕ_АКТЫ]",
        "material_violations": "[УКАЗАТЬ_СУЩЕСТВЕННЫЕ_НАРУШЕНИЯ]",
    }

    for key, value in defaults.items():
        context.setdefault(key, value)

    return context


def _normalize_template_value(value) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return "\n".join(str(item) for item in value)

    if isinstance(value, dict):
        return "\n".join(f"{key}: {item}" for key, item in value.items())

    return str(value)


def _list_to_text(items) -> str:
    if not items:
        return ""

    result = []

    for item in items:
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
            value = item.get("value") or item.get("text") or ""

            if label and value:
                result.append(f"{label}: {value}")
            elif value:
                result.append(str(value))
            elif label:
                result.append(str(label))
        else:
            result.append(str(item))

    return "\n".join(result)