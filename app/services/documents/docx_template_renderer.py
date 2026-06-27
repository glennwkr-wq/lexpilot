import base64
from io import BytesIO
from pathlib import Path

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

from app.services.documents.template_catalog import find_template_by_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def render_docx_template(
    template_id: str,
    extracted_data: dict,
    title: str = "Юридический документ",
    client_name: str = "",
    signature_data_url: str = "",
) -> BytesIO:
    template = find_template_by_id(template_id)

    if not template:
        raise FileNotFoundError("Шаблон документа не найден в каталоге.")

    template_path = PROJECT_ROOT / template["template_path"]

    if not template_path.exists():
        raise FileNotFoundError("DOCX-файл шаблона не найден.")

    document = DocxTemplate(str(template_path))
    context = build_docx_context(
        document=document,
        template=template,
        extracted_data=extracted_data,
        title=title,
        client_name=client_name,
        signature_data_url=signature_data_url,
    )

    document.render(context)

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    return file_stream


def get_docx_template_info(template_id: str | None) -> dict:
    template = find_template_by_id(template_id or "")

    if not template:
        return {
            "available": False,
            "id": "",
            "title": "",
            "path": "",
            "filename": "",
        }

    return {
        "available": True,
        "id": template.get("id") or "",
        "title": template.get("title") or "",
        "path": template.get("template_path") or "",
        "filename": Path(template.get("template_path") or "").name,
    }


def build_docx_context(
    document: DocxTemplate,
    template: dict,
    extracted_data: dict,
    title: str = "Юридический документ",
    client_name: str = "",
    signature_data_url: str = "",
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

    signature_image = _build_signature_image(document, signature_data_url)

    for variable in template.get("variables") or []:
        if variable.lower() in ["signature", "signature_image", "sign", "подпись"]:
            context[variable] = signature_image or "[ПОДПИСЬ]"
        else:
            context.setdefault(variable, f"[УКАЗАТЬ_{variable.upper()}]")

    context["signature"] = signature_image or context.get("signature") or "[ПОДПИСЬ]"
    context["signature_image"] = signature_image or ""

    return context


def _build_signature_image(document: DocxTemplate, signature_data_url: str):
    signature_data_url = (signature_data_url or "").strip()

    if not signature_data_url.startswith("data:image/png;base64,"):
        return None

    try:
        raw_base64 = signature_data_url.split(",", 1)[1]
        image_bytes = base64.b64decode(raw_base64)
    except Exception:
        return None

    return InlineImage(
        document,
        BytesIO(image_bytes),
        width=Mm(55),
    )


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