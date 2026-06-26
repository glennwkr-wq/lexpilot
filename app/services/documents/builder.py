import json
from copy import deepcopy

from app.providers.llm.openai import (
    generate_document_draft,
    generate_document_intake_json,
)
from app.services.knowledge.retrieval import (
    build_retrieval_pack,
    build_retrieval_context,
)


DOCUMENT_TYPES = {
    "claim": {
        "label": "Претензия",
        "document_type": "claim_generic",
        "keywords": ["претенз", "досудебн", "требовани"],
        "required_fields": [
            {"key": "sender", "label": "Отправитель претензии"},
            {"key": "recipient", "label": "Получатель претензии"},
            {"key": "claim_basis", "label": "Основание требований"},
            {"key": "demand", "label": "Что требуется от адресата"},
            {"key": "deadline", "label": "Срок исполнения требования"},
        ],
        "helpful_fields": [
            {"key": "contract_number", "label": "Номер договора"},
            {"key": "contract_date", "label": "Дата договора"},
            {"key": "debt_amount", "label": "Сумма задолженности"},
            {"key": "penalty_amount", "label": "Сумма неустойки"},
            {"key": "evidence", "label": "Доказательства"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "lawsuit": {
        "label": "Исковое заявление",
        "document_type": "lawsuit_generic",
        "keywords": ["иск", "исков", "взыскать через суд", "подать в суд"],
        "required_fields": [
            {"key": "court", "label": "Суд"},
            {"key": "plaintiff", "label": "Истец"},
            {"key": "defendant", "label": "Ответчик"},
            {"key": "claims", "label": "Исковые требования"},
            {"key": "facts", "label": "Фактические обстоятельства"},
            {"key": "claim_price", "label": "Цена иска, если применимо"},
        ],
        "helpful_fields": [
            {"key": "contract_number", "label": "Номер договора"},
            {"key": "contract_date", "label": "Дата договора"},
            {"key": "debt_amount", "label": "Сумма долга"},
            {"key": "penalty_amount", "label": "Сумма неустойки"},
            {"key": "state_duty", "label": "Госпошлина"},
            {"key": "pretrial_claim", "label": "Сведения о досудебной претензии"},
            {"key": "evidence", "label": "Доказательства"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "motion": {
        "label": "Ходатайство",
        "document_type": "motion_generic",
        "keywords": ["ходатайств"],
        "required_fields": [
            {"key": "court_or_body", "label": "Суд или орган"},
            {"key": "case_number", "label": "Номер дела, если есть"},
            {"key": "applicant", "label": "Заявитель"},
            {"key": "request", "label": "Суть ходатайства"},
            {"key": "grounds", "label": "Основания ходатайства"},
        ],
        "helpful_fields": [
            {"key": "participants", "label": "Участники дела"},
            {"key": "evidence", "label": "Доказательства"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "response": {
        "label": "Отзыв / возражения",
        "document_type": "response_generic",
        "keywords": ["отзыв", "возражен", "возражения на иск"],
        "required_fields": [
            {"key": "court", "label": "Суд"},
            {"key": "case_number", "label": "Номер дела"},
            {"key": "respondent", "label": "Лицо, подающее отзыв"},
            {"key": "opponent", "label": "Процессуальный оппонент"},
            {"key": "position", "label": "Позиция по требованиям"},
        ],
        "helpful_fields": [
            {"key": "arguments", "label": "Возражения по существу"},
            {"key": "evidence", "label": "Доказательства"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "appeal": {
        "label": "Апелляционная жалоба",
        "document_type": "appeal_generic",
        "keywords": ["апелляц"],
        "required_fields": [
            {"key": "appeal_court", "label": "Апелляционный суд"},
            {"key": "first_instance_court", "label": "Суд первой инстанции"},
            {"key": "case_number", "label": "Номер дела"},
            {"key": "applicant", "label": "Заявитель жалобы"},
            {"key": "decision", "label": "Какой судебный акт обжалуется"},
            {"key": "appeal_arguments", "label": "Доводы жалобы"},
        ],
        "helpful_fields": [
            {"key": "decision_date", "label": "Дата судебного акта"},
            {"key": "requested_result", "label": "Что просим у апелляции"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "cassation": {
        "label": "Кассационная жалоба",
        "document_type": "cassation_generic",
        "keywords": ["кассац"],
        "required_fields": [
            {"key": "cassation_court", "label": "Кассационный суд"},
            {"key": "case_number", "label": "Номер дела"},
            {"key": "applicant", "label": "Заявитель жалобы"},
            {"key": "challenged_acts", "label": "Обжалуемые судебные акты"},
            {"key": "material_violations", "label": "Существенные нарушения норм права"},
        ],
        "helpful_fields": [
            {"key": "requested_result", "label": "Что просим у кассации"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
    "complaint": {
        "label": "Жалоба",
        "document_type": "complaint_generic",
        "keywords": ["жалоб", "обжаловать", "оспорить отказ"],
        "required_fields": [
            {"key": "addressee", "label": "Куда подается жалоба"},
            {"key": "applicant", "label": "Заявитель"},
            {"key": "challenged_action", "label": "Что обжалуется"},
            {"key": "grounds", "label": "Основания жалобы"},
            {"key": "request", "label": "Что просим"},
        ],
        "helpful_fields": [
            {"key": "decision_date", "label": "Дата решения/действия/бездействия"},
            {"key": "authority", "label": "Орган или должностное лицо"},
            {"key": "evidence", "label": "Доказательства"},
            {"key": "attachments", "label": "Приложения"},
        ],
    },
}


UNKNOWN_DOCUMENT_SCHEMA = {
    "label": "Юридический документ",
    "document_type": "",
    "keywords": [],
    "required_fields": [
        {"key": "document_goal", "label": "Цель документа"},
        {"key": "author_or_applicant", "label": "Кто подает или направляет документ"},
        {"key": "recipient_or_opponent", "label": "Кому адресован документ"},
        {"key": "facts", "label": "Фактические обстоятельства"},
        {"key": "request", "label": "Что нужно получить в результате"},
    ],
    "helpful_fields": [
        {"key": "dates", "label": "Важные даты"},
        {"key": "amounts", "label": "Суммы"},
        {"key": "evidence", "label": "Доказательства"},
        {"key": "attachments", "label": "Приложения"},
    ],
}


def detect_document_family(user_request: str) -> dict:
    text = (user_request or "").lower()
    scores = []

    for family, config in DOCUMENT_TYPES.items():
        score = 0

        for keyword in config["keywords"]:
            if keyword in text:
                score += 3

        if config["label"].lower() in text:
            score += 4

        scores.append((score, family, config))

    scores.sort(reverse=True, key=lambda item: item[0])
    best_score, best_family, best_config = scores[0]

    if best_score <= 0:
        return {
            "family": "unknown",
            "label": UNKNOWN_DOCUMENT_SCHEMA["label"],
            "document_type": "",
            "confidence": 0.0,
        }

    return {
        "family": best_family,
        "label": best_config["label"],
        "document_type": best_config["document_type"],
        "confidence": min(1.0, best_score / 8),
    }


def build_document_from_request(
    user_request: str,
    client_context: str = "",
) -> dict:
    user_request = (user_request or "").strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    detected = detect_document_family(user_request)
    family = detected["family"]
    document_type = detected["document_type"]

    intake_schema = _build_intake_schema(family)
    retrieval_pack = build_retrieval_pack(
        family=family,
        user_request=user_request,
    )
    knowledge_context = build_retrieval_context(retrieval_pack)

    extracted_data = generate_document_intake_json(
        user_request=user_request,
        intake_schema=intake_schema,
        client_context=client_context,
        detected_family=family,
        detected_document_type=document_type,
    )

    normalized_data = _normalize_extracted_data(extracted_data)
    missing_required_fields = _get_missing_required_fields(
        intake_schema=intake_schema,
        extracted_data=normalized_data,
    )

    completeness = _calculate_completeness(
        intake_schema=intake_schema,
        missing_required_fields=missing_required_fields,
    )

    enriched_context = _build_enriched_context(
        intake_schema=intake_schema,
        extracted_data=normalized_data,
        missing_required_fields=missing_required_fields,
        knowledge_context=knowledge_context,
    )

    draft = generate_document_draft(
        user_request=user_request,
        knowledge_context=enriched_context,
        detected_family=family,
        detected_document_type=document_type,
        client_context=client_context,
    )

    return {
        "status": "ok",
        "detected_family": family,
        "detected_label": detected["label"],
        "detected_document_type": document_type,
        "detected_confidence": detected["confidence"],
        "intake_schema": intake_schema,
        "extracted_data": normalized_data,
        "missing_required_fields": missing_required_fields,
        "completeness": completeness,
        "draft": draft,
        "sources": _build_sources(retrieval_pack),
    }


def _build_intake_schema(family: str) -> dict:
    base = DOCUMENT_TYPES.get(family)

    if not base:
        base = UNKNOWN_DOCUMENT_SCHEMA

    schema = deepcopy(base)

    return {
        "family": family,
        "label": schema["label"],
        "document_type": schema.get("document_type") or "",
        "required_fields": schema["required_fields"],
        "helpful_fields": schema["helpful_fields"],
    }


def _normalize_extracted_data(extracted_data: dict | None) -> dict:
    if not isinstance(extracted_data, dict):
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": [],
        }

    fields = extracted_data.get("fields")

    if not isinstance(fields, dict):
        fields = {}

    return {
        "fields": fields,
        "parties": extracted_data.get("parties") if isinstance(extracted_data.get("parties"), dict) else {},
        "amounts": extracted_data.get("amounts") if isinstance(extracted_data.get("amounts"), list) else [],
        "dates": extracted_data.get("dates") if isinstance(extracted_data.get("dates"), list) else [],
        "risks": extracted_data.get("risks") if isinstance(extracted_data.get("risks"), list) else [],
        "notes": extracted_data.get("notes") if isinstance(extracted_data.get("notes"), list) else [],
    }


def _get_missing_required_fields(
    intake_schema: dict,
    extracted_data: dict,
) -> list[dict]:
    fields = extracted_data.get("fields") or {}
    missing = []

    for field in intake_schema.get("required_fields", []):
        key = field["key"]
        value = fields.get(key)

        if _is_empty_value(value):
            missing.append({
                "key": key,
                "label": field["label"],
            })

    return missing


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


def _calculate_completeness(
    intake_schema: dict,
    missing_required_fields: list[dict],
) -> dict:
    required_count = len(intake_schema.get("required_fields", []))
    missing_count = len(missing_required_fields)

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


def _build_enriched_context(
    intake_schema: dict,
    extracted_data: dict,
    missing_required_fields: list[dict],
    knowledge_context: str,
) -> str:
    blocks = [
        "INTAKE-СХЕМА ДОКУМЕНТА:",
        json.dumps(intake_schema, ensure_ascii=False, indent=2),
        "",
        "ИЗВЛЕЧЕННЫЕ ДАННЫЕ ИЗ ЗАПРОСА:",
        json.dumps(extracted_data, ensure_ascii=False, indent=2),
        "",
        "НЕДОСТАЮЩИЕ ОБЯЗАТЕЛЬНЫЕ ДАННЫЕ:",
        json.dumps(missing_required_fields, ensure_ascii=False, indent=2),
    ]

    if knowledge_context:
        blocks.extend([
            "",
            "МАТЕРИАЛЫ БАЗЫ ЗНАНИЙ:",
            knowledge_context,
        ])

    return "\n".join(blocks)


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

    sources = []

    for item in items:
        sources.append({
            "title": item.get("title") or "Без названия",
            "document_type": item.get("document_type") or "",
            "source_url": item.get("source_url") or "",
        })

    return sources[:5]