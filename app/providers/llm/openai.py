import json
from openai import OpenAI

from app.core.config import settings
import contextvars

client = OpenAI(api_key=settings.OPENAI_API_KEY)

_openai_usage = contextvars.ContextVar("openai_usage", default=[])


def reset_openai_usage() -> None:
    _openai_usage.set([])


def get_openai_usage_summary() -> dict:
    items = _openai_usage.get() or []

    return {
        "calls": items,
        "input_tokens": sum(item.get("input_tokens", 0) for item in items),
        "output_tokens": sum(item.get("output_tokens", 0) for item in items),
        "total_tokens": sum(item.get("total_tokens", 0) for item in items),
    }


def _log_openai_usage(stage: str, model: str, response) -> None:
    usage = getattr(response, "usage", None)

    if not usage:
        return

    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    if input_tokens is None:
        input_tokens = getattr(usage, "input_tokens", 0) or 0

    if output_tokens is None:
        output_tokens = getattr(usage, "output_tokens", 0) or 0

    if total_tokens is None:
        total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens) or 0

    item = {
        "stage": stage,
        "model": model,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens),
    }

    current = list(_openai_usage.get() or [])
    current.append(item)
    _openai_usage.set(current)

    print({
        "event": "openai_usage",
        **item,
    }, flush=True)

def generate_legal_search_queries(user_question: str) -> list[str]:
    if not settings.OPENAI_API_KEY:
        return [user_question]

    prompt = f"""
Преобразуй вопрос юриста в 3-5 поисковых запросов для поиска по корпусу нормативных правовых актов РФ.

Правила:
- не отвечай на вопрос;
- не добавляй выводы;
- верни только строки запросов, каждая с новой строки;
- используй юридические термины, названия законов, возможные формулировки из НПА;
- не выдумывай номера статей.

Вопрос:
{user_question}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помогаешь формировать поисковые запросы по российскому законодательству."},
                {"role": "user", "content": prompt.strip()},
            ],
            temperature=0.1,
        )
        _log_openai_usage("generate_search_queries", "gpt-4o-mini", response)

    except Exception:
        return [user_question]

    content = response.choices[0].message.content or ""

    queries = [
        line.strip("-• \t")
        for line in content.splitlines()
        if line.strip("-• \t")
    ]

    queries.insert(0, user_question)

    unique = []

    for query in queries:
        if query not in unique:
            unique.append(query)

    return unique[:6]

def generate_embedding(text_value: str) -> list[float]:
    text_value = (text_value or "").strip()

    if not text_value or not settings.OPENAI_API_KEY:
        return []

    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text_value[:8000],
    )
    _log_openai_usage("generate_embedding", settings.EMBEDDING_MODEL, response)
    return response.data[0].embedding


def rerank_federal_sources(
    user_question: str,
    sources: list[dict],
    limit: int = 8,
) -> list[dict]:
    if not sources or not settings.OPENAI_API_KEY:
        return sources[:limit]

    source_blocks = []

    for index, item in enumerate(sources, start=1):
        source_blocks.append(f"""
[{index}]
Название: {item.get("title")}
Тип: {item.get("document_type")}
Орган: {item.get("authority")}
Дата: {item.get("document_date")}
Номер: {item.get("document_number")}
Статус: {item.get("status")}
Метод поиска: {item.get("search_method")}
Ранг: {item.get("rank")}

Фрагмент:
{(item.get("content") or "")[:1200]}
""".strip())

    prompt = f"""
Ты юридический reranker для LexPilot.

Твоя задача — выбрать наиболее релевантные источники для ответа юристу.

Вопрос юриста:
{user_question}

Кандидаты:
{chr(10).join(source_blocks)}

Правила:
1. Верни только номера источников через запятую.
2. Основной действующий кодекс или основной федеральный закон по теме почти всегда выше:
   - закона о внесении изменений;
   - проекта закона;
   - закона о введении в действие;
   - постановления по частному вопросу;
   - исторического акта РСФСР/СССР;
   - специального регионального или переходного закона.
3. Для договоров, обязательств, подряда, неустойки, убытков, незаключенного договора приоритет имеет Гражданский кодекс РФ.
4. Для банкротства, оспаривания сделок должника, субсидиарной ответственности, требований кредиторов приоритет имеет ФЗ №127-ФЗ "О несостоятельности (банкротстве)".
5. Для гражданского процесса, апелляции, кассации, восстановления срока, оставления иска без движения приоритет имеет ГПК РФ.
6. Для трудовых споров приоритет имеет Трудовой кодекс РФ.
7. Для семейных вопросов приоритет имеет Семейный кодекс РФ.
8. Не поднимай ФЗ №154-ФЗ по Крыму и Севастополю выше 127-ФЗ по общему вопросу о банкротстве.
9. Не выбирай источник только потому, что в нём много совпадающих слов.
10. Если среди кандидатов есть базовый акт и поправочный акт к нему, сначала выбери базовый акт.
11. Максимум источников: {limit}.
"""

    try:
        response = client.chat.completions.create(
            model=settings.RERANK_MODEL,
            messages=[
                {"role": "system", "content": "Ты строго ранжируешь юридические источники по релевантности."},
                {"role": "user", "content": prompt.strip()},
            ],
            temperature=0,
        )
        _log_openai_usage("rerank_federal_sources", settings.RERANK_MODEL, response)
    except Exception:
        return sources[:limit]

    content = response.choices[0].message.content or ""
    selected_indexes = []

    for part in content.replace("\n", ",").split(","):
        part = part.strip()

        if not part.isdigit():
            continue

        value = int(part)

        if 1 <= value <= len(sources) and value not in selected_indexes:
            selected_indexes.append(value)

    reranked = [sources[index - 1] for index in selected_indexes]

    for item in sources:
        if len(reranked) >= limit:
            break

        if item not in reranked:
            reranked.append(item)

    return reranked[:limit]

def rerank_core_law_sources(
    user_question: str,
    sources: list[dict],
    limit: int = 8,
) -> list[dict]:
    if not sources or not settings.OPENAI_API_KEY:
        return sources[:limit]

    source_blocks = []

    for index, item in enumerate(sources, start=1):
        source_blocks.append(f"""
[{index}]
Кодекс: {item.get("codex")}
Статья: {item.get("article_num")}
Название статьи: {item.get("article_title")}
Глава: {item.get("chapter")}
Метод поиска: {item.get("search_method")}
Ранг: {item.get("rank")}

Текст:
{(item.get("content") or "")[:1000]}
""".strip())

    prompt = f"""
Ты юридический reranker для поиска по статьям кодексов РФ.

Вопрос юриста:
{user_question}

Кандидаты:
{chr(10).join(source_blocks)}

Правила:
1. Верни только номера источников через запятую.
2. Выбирай статьи, которые прямо отвечают на вопрос.
3. Статья с определением понятия выше статьи со второстепенным условием.
4. Если вопрос о штрафе за нетрезвое управление автомобилем — выше статья КоАП РФ об управлении транспортным средством в состоянии опьянения.
5. Если вопрос о договоре подряда — выше статья "Договор подряда".
6. Если вопрос о неустойке — выше статья "Понятие неустойки".
7. Если вопрос об общем сроке исковой давности — выше статья "Общий срок исковой давности".
8. Не выбирай соседние статьи только потому, что они из той же главы.
9. Максимум источников: {limit}.
"""

    try:
        response = client.chat.completions.create(
            model=settings.RERANK_MODEL,
            messages=[
                {"role": "system", "content": "Ты строго ранжируешь статьи кодексов РФ по юридической релевантности."},
                {"role": "user", "content": prompt.strip()},
            ],
            temperature=0,
            max_tokens=120,
            timeout=20,
        )
        _log_openai_usage("rerank_core_law_sources", settings.RERANK_MODEL, response)
    except Exception:
        return sources[:limit]

    content = response.choices[0].message.content or ""
    selected_indexes = []

    for part in content.replace("\n", ",").split(","):
        part = part.strip()

        if not part.isdigit():
            continue

        value = int(part)

        if 1 <= value <= len(sources) and value not in selected_indexes:
            selected_indexes.append(value)

    reranked = [sources[index - 1] for index in selected_indexes]

    for item in sources:
        if len(reranked) >= limit:
            break

        if item not in reranked:
            reranked.append(item)

    return reranked[:limit]

def assess_core_law_sufficiency(
    user_question: str,
    core_sources: list[dict],
) -> dict:
    if not settings.OPENAI_API_KEY:
        return {
            "is_sufficient": True,
            "confidence": 0.5,
            "reason": "OpenAI API key не настроен, используется fallback-логика.",
            "federal_search_query": user_question,
        }

    if not core_sources:
        return {
            "is_sufficient": False,
            "confidence": 1.0,
            "reason": "Статьи кодексов не найдены.",
            "federal_search_query": user_question,
        }

    source_blocks = []

    for index, item in enumerate(core_sources[:5], start=1):
        source_blocks.append(f"""
[{index}]
Кодекс: {item.get("codex")}
Статья: {item.get("article_num")}
Название статьи: {item.get("article_title")}
Текст:
{(item.get("content") or "")[:700]}
""".strip())

    prompt = f"""
Ты юридический маршрутизатор LexPilot.

Нужно решить, достаточно ли найденных статей кодексов РФ для ответа на вопрос юриста,
или нужно дополнительно искать специальный федеральный закон / иной федеральный акт в большом корпусе RusLawOD.

Вопрос юриста:
{user_question}

Найденные статьи кодексов:
{chr(10).join(source_blocks)}

Правила:
1. Ответь строго JSON без markdown.
2. is_sufficient=true, если найденные статьи кодексов прямо относятся к вопросу и позволяют дать полный рабочий юридический ответ без обязательного обращения к специальному федеральному закону.
3. Не требуй федеральный корпус только потому, что вопрос сформулирован словами "как", "порядок", "взыскать", "расторгнуть", "оспорить", "подготовить".
4. Для вопросов по алиментам, семейным обязанностям, неустойке, убыткам, исковой давности, договорам, расторжению договора, недействительности сделок, увольнению, материальной ответственности работника, наследованию и базовой гражданско-правовой ответственности статей кодексов как правило, достаточно для ответа, если найденные статьи прямо регулируют поставленный вопрос.
5. is_sufficient=false если для полного ответа необходимо обратиться к специальному федеральному закону вне кодексов. Наиболее типичные примеры: банкротство, материнский капитал, самозанятость, товарные знаки, лицензирование, государственная регистрация, ОСАГО, исполнительное производство, персональные данные, строительство, госзакупки, субсидии, специальные меры поддержки.
6. Если найденные статьи кодексов дают прямую правовую основу, но юристу могут понадобиться документы или практика, всё равно ставь is_sufficient=true.
7. federal_search_query должен быть коротким юридическим поисковым запросом для федерального корпуса.
8. Не принимай решение только по теме вопроса. В первую очередь оценивай, насколько найденные статьи кодексов действительно отвечают на поставленный вопрос.

Формат:
{{
  "is_sufficient": true,
  "confidence": 0.0,
  "reason": "краткая причина",
  "federal_search_query": "поисковый запрос"
}}
"""

    try:
        response = client.chat.completions.create(
            model=settings.RERANK_MODEL,
            messages=[
                {"role": "system", "content": "Ты строго оцениваешь достаточность найденных правовых источников."},
                {"role": "user", "content": prompt.strip()},
            ],
            temperature=0,
            max_tokens=220,
            timeout=15,
        )
        _log_openai_usage("assess_core_law_sufficiency", settings.RERANK_MODEL, response)
    except Exception:
        return {
            "is_sufficient": True,
            "confidence": 0.5,
            "reason": "Ошибка LLM-gate, используется core-law.",
            "federal_search_query": user_question,
        }

    content = response.choices[0].message.content or ""

    try:
        parsed = json.loads(content)
    except Exception:
        return {
            "is_sufficient": True,
            "confidence": 0.5,
            "reason": "LLM-gate вернул невалидный JSON.",
            "federal_search_query": user_question,
        }

    return {
        "is_sufficient": bool(parsed.get("is_sufficient")),
        "confidence": float(parsed.get("confidence") or 0),
        "reason": str(parsed.get("reason") or ""),
        "federal_search_query": str(parsed.get("federal_search_query") or user_question),
    }

def generate_legal_answer(
    user_question: str,
    knowledge_context: str = "",
) -> str:
    if not settings.OPENAI_API_KEY:
        return (
            "OpenAI API key не настроен. "
            "Добавьте OPENAI_API_KEY в переменные окружения Render."
        )

    system_prompt = """
Ты LexPilot — юридический AI-помощник для практикующего юриста.

Правила:
1. Отвечай только на основе вопроса пользователя и переданных фрагментов базы LexPilot.
2. Не выдумывай нормы права, судебную практику, пленумы, обзоры, номера статей и реквизиты актов.
3. Если в переданных источниках нет достаточной правовой базы, прямо скажи, что источников недостаточно.
4. Если переданы статьи кодексов из блока "Статья кодекса", используй их как приоритетную нормативную основу.
5. Если переданы источники RusLawOD, используй их как дополнительный или fallback-источник.
6. Федеральная база RusLawOD содержит корпус нормативных правовых актов РФ, но не является гарантией актуальной консолидированной редакции закона на текущую дату.
7. Если источник может быть исторической редакцией, укажи, что юристу нужно проверить актуальную редакцию нормы.
8. Разделяй статьи кодексов, федеральные правовые источники и локальные материалы юриста.
9. Не обещай результат дела.
10. Давай структурированный юридический ответ.
11. Отделяй факты, правовую оценку и рекомендации.
12. Любой итог является черновой правовой позицией и требует проверки юристом.
"""

    user_prompt = f"""
ВОПРОС ЮРИСТА:
{user_question}

ФРАГМЕНТЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные фрагменты базы знаний не найдены."}

Сформируй ответ строго по структуре без markdown-заголовков и без символов #:

1. Краткий вывод

2. Нормативная основа

Перечисли конкретные найденные акты из переданных источников: название, номер, дату, орган, если они указаны.
Не добавляй источники, которых нет в переданных фрагментах.

3. Правовая логика

4. Что проверить юристу

Если федеральных источников в переданном контексте нет, прямо напиши:
"В федеральной базе LexPilot релевантные источники не найдены."

Не добавляй финальную общую фразу о необходимости обратиться к актуальному законодательству, профильным комментариям или за дополнительной правовой позицией.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.2,
        max_tokens=1200,
        timeout=25,
    )
    _log_openai_usage("generate_legal_answer", "gpt-4.1-mini", response)
    return response.choices[0].message.content or ""

def generate_document_intake_json(
    user_request: str,
    intake_schema: dict,
    client_context: str = "",
    detected_family: str = "unknown",
    detected_document_type: str = "",
) -> dict:
    if not settings.OPENAI_API_KEY:
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": ["OpenAI API key не настроен."],
        }

    system_prompt = """
Ты LexPilot — модуль структурированного извлечения данных для генератора юридических документов.

Твоя задача — не писать документ, а извлечь из запроса юриста данные для intake-формы.

Правила:
1. Верни строго JSON без markdown.
2. Не выдумывай факты, даты, суммы, реквизиты, суды, адреса, ИНН, ОГРН, номера дел и номера договоров.
3. Если данных нет, верни пустую строку, пустой список или значение "не указано".
4. Не меняй роли сторон местами.
5. Если выбран клиент, используй его данные только как возможную сторону документа.
6. Не считай автоматически, что выбранный клиент — истец, заявитель, кредитор или отправитель.
7. Если роль клиента неясна, добавь это в notes.
8. Все ключи из required_fields и helpful_fields должны присутствовать в fields.
9. Дополнительные найденные сведения можно добавить в parties, amounts, dates, risks, notes.
"""

    user_prompt = f"""
ЗАПРОС ЮРИСТА:
{user_request}

ОПРЕДЕЛЕННЫЙ ТИП:
family: {detected_family}
document_type: {detected_document_type or "не определен"}

ДАННЫЕ ВЫБРАННОГО КЛИЕНТА:
{client_context if client_context else "Клиент не выбран."}

INTAKE-СХЕМА:
{json.dumps(intake_schema, ensure_ascii=False, indent=2)}

Верни JSON строго такого вида:
{{
  "fields": {{
    "ключ_поля": "значение или не указано"
  }},
  "parties": {{
    "роль": "сторона"
  }},
  "amounts": [
    {{
      "label": "что за сумма",
      "value": "сумма"
    }}
  ],
  "dates": [
    {{
      "label": "что за дата",
      "value": "дата"
    }}
  ],
  "risks": [
    "важное замечание по данным"
  ],
  "notes": [
    "что нужно учесть при генерации"
  ]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt.strip(),
                },
                {
                    "role": "user",
                    "content": user_prompt.strip(),
                },
            ],
            temperature=0,
            max_tokens=1200,
            timeout=20,
            response_format={"type": "json_object"},
        )
        _log_openai_usage("generate_document_intake_json", "gpt-4o-mini", response)
    except Exception as error:
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": [f"Ошибка извлечения данных: {error}"],
        }

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
    except Exception:
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": ["Модель вернула невалидный JSON."],
        }

    if not isinstance(parsed, dict):
        return {
            "fields": {},
            "parties": {},
            "amounts": [],
            "dates": [],
            "risks": [],
            "notes": ["Модель вернула JSON не в виде объекта."],
        }

    return parsed

def generate_document_draft(
    user_request: str,
    knowledge_context: str = "",
    detected_family: str = "unknown",
    detected_document_type: str = "",
    client_context: str = "",
) -> str:
    if not settings.OPENAI_API_KEY:
        return (
            "OpenAI API key не настроен. "
            "Добавьте OPENAI_API_KEY в переменные окружения Render."
        )

    system_prompt = """
Ты LexPilot — профессиональный юридический drafting assistant для практикующего юриста.

Твоя задача — подготовить рабочий черновик документа на основе:
1. запроса юриста;
2. найденного шаблона документа;
3. найденной intake form;
4. материалов базы знаний LexPilot.

Ключевые правила:
1. Не объясняй, что такое документ.
2. Не пиши учебные вводные.
3. Не выдумывай факты, даты, суммы, реквизиты, нормы права или судебную практику.
4. Если данных не хватает, перечисли недостающие данные.
5. Если шаблон найден, строго используй его структуру.
6. Если intake form найдена, проверь запрос по обязательным данным из нее.
7. Если данных достаточно, подготовь полноценный черновик.
8. Если данных не хватает, всё равно подготовь предварительный каркас с плейсхолдерами.
9. Документ является черновиком и требует проверки юристом.
10. Внимательно определяй роли сторон из запроса. Если указаны поставщик, покупатель, исполнитель, заказчик, истец, ответчик, заявитель, адресат — не меняй их местами.
11. Используй как основной шаблон только документ с DOCUMENT_TYPE, совпадающим с определенным типом документа. Остальные материалы используй только как вспомогательные чек-листы или справку.
12. Если переданы данные выбранного клиента, используй их только как данные возможной стороны документа.
13. Не считай автоматически, что выбранный клиент всегда является истцом, заявителем, кредитором или отправителем претензии. Роль клиента определяй по запросу юриста.
14. Если роль клиента из запроса неясна, укажи это в разделе проверки обязательных данных.
15. Не выдумывай реквизиты клиента. Используй только те данные клиента, которые переданы явно.
"""

    user_prompt = f"""
ЗАПРОС ЮРИСТА:
{user_request}

ОПРЕДЕЛЕННЫЙ ТИП ДОКУМЕНТА:
family: {detected_family}
document_type: {detected_document_type or "не определен"}

ДАННЫЕ КЛИЕНТА ИЗ БАЗЫ LEXPILOT:
{client_context if client_context else "Клиент не выбран."}

МАТЕРИАЛЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные материалы базы знаний не найдены."}

Сформируй результат строго в формате:

1. Тип документа

Укажи определенный тип документа.

2. Проверка обязательных данных

Используй INTAKE-СХЕМУ, ИЗВЛЕЧЕННЫЕ ДАННЫЕ и НЕДОСТАЮЩИЕ ОБЯЗАТЕЛЬНЫЕ ДАННЫЕ из материалов базы LexPilot.

Раздели данные на:
- данные есть;
- данных не хватает.

Если обязательных данных не хватает, перечисли только конкретные недостающие поля.
Не задавай общие вопросы вроде "уточните обстоятельства".

3. Черновик документа

Подготовь документ по найденной структуре.

Если каких-то данных нет, используй плейсхолдеры вида:
[УКАЗАТЬ_...]

Не вставляй разделы "тип документа" и "проверка данных" внутрь самого юридического документа.
Юридический документ должен начинаться как реальный документ: с адресата, сторон, названия или вводной части.

4. Что проверить юристу

Краткий список проверки перед использованием.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.1,
    )
    _log_openai_usage("generate_document_draft", "gpt-4.1-mini", response)
    return response.choices[0].message.content or ""

def analyze_legal_document(
    document_text: str,
    knowledge_context: str = "",
) -> str:
    if not settings.OPENAI_API_KEY:
        return (
            "OpenAI API key не настроен. "
            "Добавьте OPENAI_API_KEY в переменные окружения Render."
        )

    system_prompt = """
Ты LexPilot — юридический AI-инструмент для анализа документов.

Твоя задача — помочь юристу быстро оценить документ.

Правила:
1. Не выдумывай факты, которых нет в документе.
2. Не обещай исход дела.
3. Не придумывай судебную практику, если её нет в базе знаний.
4. Анализируй строго по тексту документа.
5. Отделяй факты, риски, спорные места и рекомендации.
6. Итог является аналитической заметкой и требует проверки юристом.
"""

    user_prompt = f"""
ТЕКСТ ДОКУМЕНТА:
{document_text}

МАТЕРИАЛЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные материалы базы знаний не найдены."}

Сформируй анализ строго в формате:

1. Тип документа

2. Краткое содержание

3. Ключевые условия / обстоятельства

4. Потенциальные риски

5. Спорные или слабые места

6. Что проверить юристу

7. Практические рекомендации
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.15,
    )
    _log_openai_usage("analyze_legal_document", "gpt-4o-mini", response)
    return response.choices[0].message.content or ""