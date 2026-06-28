import re


EXACT_LABELS = {
    "court": "Суд",
    "court_name": "Наименование суда",
    "court_name_text": "Наименование суда",
    "court_address": "Адрес суда",
    "in_court_name": "В какой суд подается документ",

    "plaintiff": "Истец",
    "plaintiff_name": "ФИО / наименование истца",
    "plaintiff_fio": "ФИО истца",
    "plaintiff_address": "Адрес истца",
    "plaintiff_passport": "Паспортные данные истца",
    "plaintiff_registration_address": "Адрес регистрации истца",
    "plaintiff_details": "Данные истца",
    "plaintiff_role": "Роль истца",
    "plaintiff_obligation": "Обязанность истца",
    "plaintiff_representative": "Представитель истца",

    "defendant": "Ответчик",
    "defendant_name": "ФИО / наименование ответчика",
    "defendant_address": "Адрес ответчика",
    "defendant_passport": "Паспортные данные ответчика",
    "defendant_registration_address": "Адрес регистрации ответчика",
    "defendant_details": "Данные ответчика",
    "defendant_role": "Роль ответчика",
    "defendant_obligation": "Обязанность ответчика",
    "defendant_belief": "Позиция ответчика",

    "applicant": "Заявитель",
    "applicant_passport": "Паспортные данные заявителя",
    "applicant_registration_address": "Адрес регистрации заявителя",
    "applicant_role": "Роль заявителя",

    "signature": "Подпись",
    "signatory_name": "ФИО подписанта",
    "document_date": "Дата документа",
    "document_city": "Город составления документа",

    "claim_price": "Цена иска",
    "state_duty": "Госпошлина",
    "state_duty_amount": "Размер госпошлины",
    "claim_subject": "Предмет требований",
    "claim_demands": "Требования",
    "claim_requests": "Просительная часть",
    "claim_facts": "Фактические обстоятельства",
    "claim_details": "Обстоятельства требований",
    "claim_attachments": "Приложения к иску",

    "debt_amount": "Сумма задолженности",
    "amount_of_debt": "Сумма задолженности",
    "total_debt_amount": "Общая сумма задолженности",
    "penalty_amount": "Сумма неустойки",
    "interest_amount": "Сумма процентов",
    "moral_damage_amount": "Размер морального вреда",
    "moral_compensation_amount": "Размер компенсации морального вреда",

    "contract_type": "Вид договора",
    "contract_number": "Номер договора",
    "contract_num": "Номер договора",
    "contract_date": "Дата договора",
    "contract_price": "Цена договора",
    "contract_subject": "Предмет договора",
    "contract_details": "Условия договора",
    "contract_obligations": "Обязательства по договору",

    "marriage_date": "Дата заключения брака",
    "divorce_reasons": "Причины расторжения брака",
    "children_name": "ФИО детей",
    "children_birth_year": "Год рождения детей",
    "children_date_of_birth": "Дата рождения детей",
    "upbringing_conditions": "Условия воспитания детей",

    "attachments": "Приложения",
    "attachments_list": "Список приложений",
    "evidence": "Доказательства",
    "evidence_list": "Список доказательств",
    "legal_grounds": "Правовые основания",
    "additional_request": "Дополнительное требование",
}


TOKEN_LABELS = {
    "accident": "ДТП",
    "accommodation": "проживание",
    "account": "счет",
    "act": "акт",
    "actual": "фактический",
    "additional": "дополнительный",
    "address": "адрес",
    "agreement": "соглашение",
    "airline": "авиакомпания",
    "alimony": "алименты",
    "amount": "сумма",
    "apartment": "квартира",
    "applicant": "заявитель",
    "application": "заявление",
    "arrears": "задолженность",
    "arrival": "прибытие",
    "article": "статья",
    "attachment": "приложение",
    "attachments": "приложения",
    "bank": "банк",
    "birth": "рождение",
    "borrower": "заемщик",
    "buyer": "покупатель",
    "cadastral": "кадастровый",
    "case": "дело",
    "child": "ребенок",
    "children": "дети",
    "citizenship": "гражданство",
    "city": "город",
    "claim": "требование",
    "claims": "требования",
    "client": "клиент",
    "company": "организация",
    "compensation": "компенсация",
    "complaint": "жалоба",
    "contract": "договор",
    "contractor": "исполнитель",
    "court": "суд",
    "creditor": "кредитор",
    "current": "текущий",
    "damage": "ущерб",
    "date": "дата",
    "debt": "задолженность",
    "debtor": "должник",
    "defendant": "ответчик",
    "delay": "просрочка",
    "delivery": "поставка",
    "demand": "требование",
    "departure": "отправление",
    "details": "данные",
    "divorce": "расторжение брака",
    "document": "документ",
    "employer": "работодатель",
    "employment": "работа",
    "evidence": "доказательства",
    "event": "событие",
    "expertise": "экспертиза",
    "facts": "обстоятельства",
    "family": "семья",
    "fee": "пошлина",
    "fio": "ФИО",
    "grounds": "основания",
    "heir": "наследник",
    "income": "доход",
    "incident": "происшествие",
    "info": "сведения",
    "interest": "проценты",
    "issue": "вопрос",
    "law": "закон",
    "legal": "правовой",
    "lender": "займодавец",
    "lessee": "арендатор",
    "lessor": "арендодатель",
    "list": "список",
    "loan": "заем",
    "location": "место",
    "loss": "убыток",
    "marriage": "брак",
    "moral": "моральный",
    "name": "наименование / ФИО",
    "number": "номер",
    "obligation": "обязанность",
    "obligations": "обязанности",
    "offender": "нарушитель",
    "order": "приказ / порядок",
    "organization": "организация",
    "passport": "паспортные данные",
    "payment": "платеж",
    "penalty": "неустойка",
    "period": "период",
    "person": "лицо",
    "plaintiff": "истец",
    "price": "цена",
    "property": "имущество",
    "recipient": "получатель / адресат",
    "registration": "регистрация",
    "representative": "представитель",
    "request": "требование / просьба",
    "requisites": "реквизиты",
    "residence": "место жительства",
    "role": "роль",
    "seller": "продавец",
    "sender": "отправитель",
    "service": "услуга",
    "signature": "подпись",
    "subject": "предмет",
    "sum": "сумма",
    "tenant": "наниматель / арендатор",
    "text": "текст",
    "total": "общий",
    "vehicle": "транспортное средство",
    "violation": "нарушение",
    "witness": "свидетель",
    "work": "работа",
    "year": "год",
}


def get_field_label(variable: str) -> str:
    key = normalize_key(variable)

    if key in EXACT_LABELS:
        return EXACT_LABELS[key]

    words = [word for word in key.split("_") if word]

    if not words:
        return "Поле документа"

    translated = []

    for word in words:
        translated.append(TOKEN_LABELS.get(word, word))

    label = " ".join(translated)
    label = re.sub(r"\s+", " ", label).strip()

    return label[:1].upper() + label[1:] if label else "Поле документа"


def normalize_key(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"&[a-zA-Z]+;", " ", value)
    value = re.sub(r"\{[{%].*?[%}]\}", " ", value)
    value = value.replace("-", "_")
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_").lower()