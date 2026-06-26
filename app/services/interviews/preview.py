def build_document_preview(interview_result: dict) -> str:
    interview = interview_result.get("interview") or {}
    data = interview_result.get("data") or {}
    fields = data.get("fields") or {}

    label = interview_result.get("label") or "Юридический документ"
    missing = interview_result.get("missing_required_fields") or []
    sections = interview.get("sections") or []

    lines = []

    lines.append(f"Тип документа: {label}")
    lines.append("")
    lines.append("Проверка данных:")

    if missing:
        lines.append("Не хватает:")
        for field in missing:
            lines.append(f"- {field.get('label') or field.get('key')}")
    else:
        lines.append("Критичных пропусков по обязательным полям не найдено.")

    lines.append("")
    lines.append("Предварительная структура документа:")
    lines.append("")

    if not sections:
        lines.append("Структура документа будет сформирована по Word-шаблону.")
        return "\n".join(lines)

    for section in sections:
        title = section.get("title") or ""
        body = section.get("body") or ""

        if title:
            lines.append(title)
            lines.append("")

        if body:
            lines.append(_render_text(body, fields))
            lines.append("")

    return "\n".join(lines).strip()


def _render_text(text: str, fields: dict) -> str:
    result = text

    for key, value in fields.items():
        result = result.replace("{{ " + key + " }}", str(value or ""))
        result = result.replace("{{" + key + "}}", str(value or ""))

    return result