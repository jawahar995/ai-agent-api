from langchain.tools import tool
from src.agents.vector_store import get_vector_store

def build_retriever_tool(config: dict):
    db_type = config.get("db_type") or config.get("type") or "qdrant"
    kb_id = config.get("kb_id")
    collection_name = f"kb_{kb_id}" if kb_id else "kb_collection"
    
    embedding_type = config.get("embedding_type") or config.get("provider") or "openai"
    embedding_model = config.get("embedding_model")
    embedding_api_key = config.get("embedding_api_key")
    
    vectorstore_config = {
        "type": db_type,
        "collection_name": collection_name,
        "embedding_type": embedding_type,
        "embedding_model": embedding_model,
        "embedding_api_key": embedding_api_key,
    }
    
    if db_type == "qdrant":
        from src.utils.config import config as app_config
        vectorstore_config["url"] = f"http://{app_config.vector_store_url}:{app_config.vector_store_port}"
        vectorstore_config["api_key"] = app_config.vector_store_api_key
        
    vectorstore = get_vector_store(vectorstore_config)
    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 3
        }
    )

    @tool
    async def retriever_tool(query: str) -> str:
        """
        Search KB documents using semantic search.
        """

        docs = await retriever.ainvoke(query)

        if not docs:
            return "No KB results found"

        results = []

        for doc in docs:
            results.append(doc.page_content)

        return "\n".join(results)

    return retriever_tool