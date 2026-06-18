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
) -> str:
    if not settings.OPENAI_API_KEY:
        return (
            "OpenAI API key не настроен. "
            "Добавьте OPENAI_API_KEY в переменные окружения Render."
        )

    system_prompt = """
Ты LexPilot — профессиональный юридический AI-инструмент для практикующего юриста.

Твоя задача — не объяснять юристу, что такое документ, а подготовить рабочий черновик документа.

Правила:
1. Работай как юридический drafting assistant.
2. Не давай вводных лекций.
3. Не придумывай нормы, судебную практику, реквизиты, даты, суммы или факты.
4. Если данных не хватает, сначала перечисли недостающие данные.
5. Если данных достаточно, подготовь документ в деловом юридическом стиле.
6. Используй найденные материалы базы знаний, шаблоны, чек-листы и сценарии.
7. Если релевантной базы знаний недостаточно, прямо укажи это.
8. Документ должен быть пригоден для дальнейшей правки юристом.
"""

    user_prompt = f"""
ЗАПРОС ЮРИСТА:
{user_request}

МАТЕРИАЛЫ БАЗЫ ЗНАНИЙ LEXPILOT:
{knowledge_context if knowledge_context else "Релевантные материалы базы знаний не найдены."}

Сформируй результат строго в формате:

1. Тип документа
2. Достаточно ли данных для подготовки
3. Недостающие данные, если они есть
4. Черновик документа
5. Что юристу проверить перед использованием

Если данных для полноценного документа недостаточно, всё равно подготовь предварительный каркас документа с пометками [указать ...].
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.15,
    )

    return response.choices[0].message.content or ""