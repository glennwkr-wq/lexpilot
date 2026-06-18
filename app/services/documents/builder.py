from app.providers.llm.openai import generate_document_draft
from app.services.knowledge.search import search_knowledge, build_knowledge_context


def build_document_from_request(user_request: str) -> dict:
    user_request = user_request.strip()

    if not user_request:
        return {
            "status": "error",
            "message": "Запрос пустой.",
        }

    knowledge_results = search_knowledge(user_request, limit=8)
    knowledge_context = build_knowledge_context(knowledge_results)

    draft = generate_document_draft(
        user_request=user_request,
        knowledge_context=knowledge_context,
    )

    return {
        "status": "ok",
        "draft": draft,
        "sources": [
            {
                "title": item["title"],
                "document_type": item["document_type"],
                "source_url": item["source_url"],
            }
            for item in knowledge_results
        ],
    }