from copy import deepcopy

from app.providers.llm.openai import generate_document_intake_json
from app.services.interviews.loader import (
    get_required_fields,
    get_visible_fields,
    list_interview_fields,
)
from app.services.interviews.schemas import detect_document_family


def start_or_update_interview(
    user_request: str,
    client_context: str = "",
    previous_data: dict | None = None,
    answers: dict | None = None,
    forced_family: str | None = None,
) -> dict:
    from app.services.interviews.loader import load_interview

    user_request = (user_request or "").strip()

    detected = detect_document_family(user_request)

    if forced_family:
        detected["family"] = forced_family

    family = detected["family"]
    interview = load_interview(family)

    data = _normalize_data(previous_data)

    first_run = not bool(data.get("fields"))

    if first_run:
        extraction_schema = _build_extraction_schema(interview)

        extracted = generate_document_intake_json(
            user_request=user_request,
            intake_schema=extraction_schema,
            client_context=client_context,
            detected_family=family,
            detected_document_type=interview.get("template") or "",
        )

        data = _normalize_data(extracted)

    if isinstance(answers, dict) and answers:
        data = merge_answers(data, answers)

    visible_fields = get_visible_fields(interview, data.get("fields") or {})
    missing_required_fields = get_missing_required_fields(interview, data)
    completeness = calculate_completeness(interview, missing_required_fields)

    return {
        "family": family,
        "label": interview.get("label") or detected.get("label") or "Юридический документ",
        "confidence": detected.get("confidence", 0),
        "interview": interview,
        "data": data,
        "visible_fields": visible_fields,
        "missing_required_fields": missing_required_fields,
        "completeness": completeness,
        "first_run": first_run,
    }


def merge_answers(data: dict, answers: dict) -> dict:
    normalized = _normalize_data(data)
    fields = normalized["fields"]

    for key, value in answers.items():
        if value is None:
            continue

        if isinstance(value, str):
            clean_value = value.strip()

            if not clean_value:
                continue

            fields[key] = clean_value
            continue

        fields[key] = value

    normalized["fields"] = fields
    return normalized


def get_missing_required_fields(interview: dict, data: dict) -> list[dict]:
    fields = data.get("fields") or {}
    missing = []

    visible_required_fields = [
        field
        for field in get_required_fields(interview)
        if field in get_visible_fields(interview, fields)
    ]

    for field in visible_required_fields:
        key = field.get("key")
        value = fields.get(key)

        if _is_empty_value(value):
            missing.append({
                "key": key,
                "label": field.get("label") or key,
                "type": field.get("type") or "text",
                "help": field.get("help") or "",
                "placeholder": field.get("placeholder") or "",
                "choices": field.get("choices") or [],
            })

    return missing


def calculate_completeness(interview: dict, missing_required_fields: list[dict]) -> dict:
    required_count = len(get_required_fields(interview))
    missing_count = len(missing_required_fields)

    if required_count <= 0:
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


def _build_extraction_schema(interview: dict) -> dict:
    required_fields = []
    helpful_fields = []

    for field in list_interview_fields(interview):
        item = {
            "key": field.get("key"),
            "label": field.get("label") or field.get("key"),
        }

        if field.get("required"):
            required_fields.append(item)
        else:
            helpful_fields.append(item)

    return {
        "family": interview.get("family"),
        "label": interview.get("label"),
        "document_type": interview.get("template") or "",
        "required_fields": required_fields,
        "helpful_fields": helpful_fields,
    }


def _normalize_data(data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": [],
        }

    fields = data.get("fields")
    parties = data.get("parties")
    amounts = data.get("amounts")
    dates = data.get("dates")
    risks = data.get("risks")
    notes = data.get("notes")

    return {
        "fields": deepcopy(fields) if isinstance(fields, dict) else {},
        "parties": deepcopy(parties) if isinstance(parties, dict) else {},
        "amounts": deepcopy(amounts) if isinstance(amounts, list) else [],
        "dates": deepcopy(dates) if isinstance(dates, list) else [],
        "risks": deepcopy(risks) if isinstance(risks, list) else [],
        "notes": deepcopy(notes) if isinstance(notes, list) else [],
    }


def _is_empty_value(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        clean_value = value.strip()

        return (
            not clean_value
            or clean_value == "не указано"
            or clean_value.startswith("[УКАЗАТЬ")
        )

    if isinstance(value, list):
        return len(value) == 0

    return False