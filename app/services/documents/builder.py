from app.providers.llm.openai import generate_document_intake_json
from app.services.documents.template_catalog import choose_best_template, search_templates
from app.services.documents.docx_template_renderer import get_docx_template_info


def build_document_from_request(
    user_request: str,
    client_context: str = "",
    previous_data: dict | None = None,
    answers: dict | None = None,
    selected_template_id: str | None = None,
) -> dict:
    user_request = (user_request or "").strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    previous_data = previous_data if isinstance(previous_data, dict) else None
    answers = answers if isinstance(answers, dict) else {}

    family = detect_family(user_request)

    template = None

    if selected_template_id:
        from app.services.documents.template_catalog import find_template_by_id
        template = find_template_by_id(selected_template_id)

    if not template:
        template = choose_best_template(
            query=user_request,
            family=family,
        )

    if not template:
        candidate_templates = search_templates(user_request, family=None, limit=8)
        template = candidate_templates[0] if candidate_templates else None

    if not template:
        return {
            "status": "error",
            "message": "Шаблоны документов не найдены. Сначала импортируйте российскую библиотеку шаблонов.",
        }

    data = normalize_data(previous_data)

    if not data["fields"]:
        intake_schema = build_intake_schema_from_template(template)

        extracted = generate_document_intake_json(
            user_request=user_request,
            intake_schema=intake_schema,
            client_context=client_context,
            detected_family=template.get("family") or family,
            detected_document_type=template.get("title") or "",
        )

        data = normalize_data(extracted)

    data = merge_answers(data, answers)

    fields = build_fields_from_template(template)
    missing_fields = find_missing_fields(fields, data)
    current_question = find_next_question(fields, data)

    completeness = calculate_completeness(fields, missing_fields)
    draft = build_preview(template, fields, data, missing_fields)

    template_id = template.get("id") or ""

    return {
        "status": "ok",
        "detected_family": template.get("family") or family,
        "detected_label": family_label(template.get("family") or family),
        "detected_document_type": template.get("title") or "",
        "selected_template": {
            "id": template_id,
            "title": template.get("title") or "",
            "family": template.get("family") or "",
            "category": template.get("category") or "",
            "subcategory": template.get("subcategory") or "",
            "template_path": template.get("template_path") or "",
        },
        "candidate_templates": search_templates(user_request, family=template.get("family"), limit=8),
        "extracted_data": data,
        "fields": fields,
        "missing_required_fields": missing_fields,
        "current_question": current_question,
        "completeness": completeness,
        "draft": draft,
        "sources": build_sources(template),
        "docx_template": get_docx_template_info(template_id),
    }


def detect_family(user_request: str) -> str:
    text = user_request.lower()

    if "претенз" in text or "досудеб" in text:
        return "claim"

    if "иск" in text or "исков" in text or "в суд" in text:
        return "lawsuit"

    if "договор" in text or "соглашение" in text:
        return "contract"

    if "жалоб" in text or "обжал" in text:
        return "complaint"

    if "ходатай" in text:
        return "motion"

    return "document"


def family_label(family: str) -> str:
    return {
        "claim": "Претензия",
        "lawsuit": "Исковое заявление",
        "contract": "Договор",
        "complaint": "Жалоба",
        "motion": "Ходатайство",
        "document": "Юридический документ",
    }.get(family, "Юридический документ")


def build_intake_schema_from_template(template: dict) -> dict:
    variables = template.get("variables") or []

    required_fields = []
    helpful_fields = []

    for variable in variables:
        item = {
            "key": variable,
            "label": label_from_variable(variable, template),
        }

        if is_required_variable(variable):
            required_fields.append(item)
        else:
            helpful_fields.append(item)

    return {
        "family": template.get("family") or "",
        "label": template.get("title") or "Юридический документ",
        "document_type": template.get("title") or "",
        "required_fields": required_fields,
        "helpful_fields": helpful_fields,
    }


def build_fields_from_template(template: dict) -> list[dict]:
    variables = template.get("variables") or []
    fields = []

    for variable in variables:
        fields.append({
            "key": variable,
            "label": label_from_variable(variable, template),
            "type": guess_field_type(variable),
            "required": is_required_variable(variable),
            "placeholder": "",
            "help": "",
        })

    return fields


def label_from_variable(variable: str, template: dict) -> str:
    variable_map = template.get("variable_map") or {}

    for original, normalized in variable_map.items():
        if normalized == variable:
            return cleanup_label(original)

    return cleanup_label(variable)


def cleanup_label(value: str) -> str:
    value = value.replace("_", " ")
    value = value.strip()

    replacements = {
        "court name": "Наименование суда",
        "court address": "Адрес суда",
        "plaintiff": "Истец",
        "defendant": "Ответчик",
        "signature": "Подпись",
        "claim price": "Цена иска",
        "state duty": "Госпошлина",
        "date": "Дата",
        "city": "Город",
    }

    return replacements.get(value.lower(), value[:1].upper() + value[1:])


def guess_field_type(variable: str) -> str:
    text = variable.lower()

    if any(word in text for word in ["description", "claim_list", "claims", "circumstances", "grounds", "basis"]):
        return "textarea"

    if "date" in text:
        return "text"

    if "amount" in text or "price" in text or "duty" in text:
        return "text"

    return "text"


def is_required_variable(variable: str) -> bool:
    text = variable.lower()

    optional_words = [
        "representative",
        "second",
        "third",
        "penalty",
        "moral",
        "additional",
    ]

    if any(word in text for word in optional_words):
        return False

    return True


def normalize_data(data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": [],
        }

    return {
        "fields": data.get("fields") if isinstance(data.get("fields"), dict) else {},
        "parties": data.get("parties") if isinstance(data.get("parties"), dict) else {},
        "amounts": data.get("amounts") if isinstance(data.get("amounts"), list) else [],
        "dates": data.get("dates") if isinstance(data.get("dates"), list) else [],
        "risks": data.get("risks") if isinstance(data.get("risks"), list) else [],
        "notes": data.get("notes") if isinstance(data.get("notes"), list) else [],
    }


def merge_answers(data: dict, answers: dict) -> dict:
    fields = data.get("fields") or {}

    for key, value in answers.items():
        if value is None:
            continue

        if isinstance(value, str):
            value = value.strip()

        if value:
            fields[key] = value

    data["fields"] = fields
    return data


def find_missing_fields(fields: list[dict], data: dict) -> list[dict]:
    values = data.get("fields") or {}
    missing = []

    for field in fields:
        if not field.get("required"):
            continue

        key = field.get("key")
        value = values.get(key)

        if is_empty(value):
            missing.append(field)

    return missing


def find_next_question(fields: list[dict], data: dict) -> dict | None:
    values = data.get("fields") or {}

    for field in fields:
        if not is_empty(values.get(field.get("key"))):
            continue

        return field

    return None


def is_empty(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        clean = value.strip()
        return not clean or clean == "не указано" or clean.startswith("[УКАЗАТЬ")

    if isinstance(value, list):
        return len(value) == 0

    return False


def calculate_completeness(fields: list[dict], missing: list[dict]) -> dict:
    required = [field for field in fields if field.get("required")]
    required_count = len(required)
    missing_count = len(missing)

    if required_count == 0:
        percent = 100
    else:
        percent = round(((required_count - missing_count) / required_count) * 100)

    if percent >= 90:
        level = "high"
        label = "Данных достаточно"
    elif percent >= 60:
        level = "medium"
        label = "Данных частично достаточно"
    else:
        level = "low"
        label = "Данных мало"

    return {
        "required_count": required_count,
        "missing_count": missing_count,
        "percent": percent,
        "level": level,
        "label": label,
    }


def build_preview(template: dict, fields: list[dict], data: dict, missing: list[dict]) -> str:
    values = data.get("fields") or {}

    lines = [
        f"Выбранный шаблон: {template.get('title')}",
        f"Категория: {template.get('category')}",
    ]

    if template.get("subcategory"):
        lines.append(f"Подкатегория: {template.get('subcategory')}")

    lines.append("")
    lines.append("Заполненные данные:")

    filled = [
        field
        for field in fields
        if not is_empty(values.get(field.get("key")))
    ]

    if filled:
        for field in filled[:20]:
            lines.append(f"- {field.get('label')}: {values.get(field.get('key'))}")
    else:
        lines.append("- Пока нет заполненных данных.")

    lines.append("")
    lines.append("Чего не хватает:")

    if missing:
        for field in missing[:20]:
            lines.append(f"- {field.get('label')}")
    else:
        lines.append("- Критичных пропусков нет.")

    lines.append("")
    lines.append("Итоговый документ будет сформирован по российскому Word-шаблону.")

    return "\n".join(lines)


def build_sources(template: dict) -> list[dict]:
    return [
        {
            "title": template.get("title") or "Российский Word-шаблон",
            "document_type": template.get("family") or "docx_template",
            "source_url": template.get("source_path") or template.get("template_path") or "",
        }
    ]