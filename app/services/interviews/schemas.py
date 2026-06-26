DOCUMENT_FAMILY_LABELS = {
    "claim": "Претензия",
    "lawsuit": "Исковое заявление",
    "motion": "Ходатайство",
    "response": "Отзыв / возражения",
    "appeal": "Апелляционная жалоба",
    "cassation": "Кассационная жалоба",
    "complaint": "Жалоба",
    "unknown": "Юридический документ",
}


DOCUMENT_FAMILY_KEYWORDS = {
    "claim": ["претенз", "досудебн", "требовани"],
    "lawsuit": ["иск", "исков", "взыскать через суд", "подать в суд"],
    "motion": ["ходатайств"],
    "response": ["отзыв", "возражен", "возражения на иск"],
    "appeal": ["апелляц"],
    "cassation": ["кассац"],
    "complaint": ["жалоб", "обжаловать", "оспорить отказ"],
}


def detect_document_family(user_request: str) -> dict:
    text = (user_request or "").lower()
    best_family = "unknown"
    best_score = 0

    for family, keywords in DOCUMENT_FAMILY_KEYWORDS.items():
        score = 0

        for keyword in keywords:
            if keyword in text:
                score += 3

        if score > best_score:
            best_score = score
            best_family = family

    return {
        "family": best_family,
        "label": DOCUMENT_FAMILY_LABELS.get(best_family, "Юридический документ"),
        "confidence": min(1.0, best_score / 6) if best_score else 0.0,
    }