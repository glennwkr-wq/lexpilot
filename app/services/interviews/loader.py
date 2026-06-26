from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INTERVIEWS_ROOT = PROJECT_ROOT / "interviews" / "document_builder"


def load_interview(family: str) -> dict:
    family = family or "unknown"
    path = INTERVIEWS_ROOT / f"{family}.yml"

    if not path.exists():
        path = INTERVIEWS_ROOT / "unknown.yml"

    if not path.exists():
        raise FileNotFoundError("Interview-сценарий не найден.")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    data.setdefault("family", family)
    data.setdefault("label", "Юридический документ")
    data.setdefault("template", "")
    data.setdefault("fields", [])
    data.setdefault("sections", [])

    return data


def list_interview_fields(interview: dict) -> list[dict]:
    fields = interview.get("fields")

    if not isinstance(fields, list):
        return []

    return [field for field in fields if isinstance(field, dict)]


def get_required_fields(interview: dict) -> list[dict]:
    return [
        field
        for field in list_interview_fields(interview)
        if bool(field.get("required"))
    ]


def get_visible_fields(interview: dict, data_fields: dict) -> list[dict]:
    visible = []

    for field in list_interview_fields(interview):
        show_if = field.get("show_if")

        if not _passes_show_if(show_if, data_fields):
            continue

        visible.append(field)

    return visible


def _passes_show_if(show_if, data_fields: dict) -> bool:
    if not show_if:
        return True

    if not isinstance(show_if, dict):
        return True

    key = show_if.get("field")
    equals = show_if.get("equals")
    not_empty = show_if.get("not_empty")

    if not key:
        return True

    value = data_fields.get(key)

    if equals is not None:
        return str(value).strip().lower() == str(equals).strip().lower()

    if not_empty:
        return not _is_empty(value)

    return True


def _is_empty(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        clean = value.strip()
        return not clean or clean == "не указано" or clean.startswith("[УКАЗАТЬ")

    if isinstance(value, list):
        return len(value) == 0

    return False