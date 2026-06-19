from openai import OpenAI

from app.core.config import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)


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
Ты LexPilot — юридический AI-помощник для юриста.

Правила:
1. Не выдумывай нормы права, судебную практику, пленумы и обзоры.
2. Если информации в базе знаний недостаточно, прямо скажи об этом.
3. Не обещай результат дела.
4. Давай структурированный юридический ответ.
5. Отделяй факты, правовую оценку, риски и рекомендации.
6. Любой итоговый документ является черновиком и требует проверки юристом.
"""

    user_prompt = f"""
ВОПРОС ЮРИСТА:
{user_question}

ФРАГМЕНТЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные фрагменты базы знаний не найдены."}

Сформируй ответ:
- краткий вывод;
- правовая логика;
- риски;
- что проверить юристу;
- какие данные нужны дополнительно.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""

def generate_document_draft(
    user_request: str,
    knowledge_context: str = "",
    detected_family: str = "unknown",
    detected_document_type: str = "",
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
"""

    user_prompt = f"""
ЗАПРОС ЮРИСТА:
{user_request}

ОПРЕДЕЛЕННЫЙ ТИП ДОКУМЕНТА:
family: {detected_family}
document_type: {detected_document_type or "не определен"}

МАТЕРИАЛЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные материалы базы знаний не найдены."}

Сформируй результат строго в формате:

## 1. Тип документа

Укажи определенный тип документа.

## 2. Проверка обязательных данных

Проверь запрос по intake form, если она есть в материалах.

Раздели данные на:
- данные есть;
- данных не хватает.

## 3. Черновик документа

Подготовь документ по найденному шаблону.

Если каких-то данных нет, используй плейсхолдеры вида:
[УКАЗАТЬ_...]

## 4. Что проверить юристу

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

    return response.choices[0].message.content or ""