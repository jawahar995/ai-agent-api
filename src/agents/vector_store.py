from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from src.agents.embedding import configure_embedding



def get_vector_store(config):
    embedding_model = config["embedding_model"]
    api_key = config["embedding_api_key"]
    embeddings = configure_embedding(
        embedding_type=config["embedding_type"],
        embedding_model=embedding_model,
        api_key=api_key
    )
    if config["type"] == "chroma":
        import chromadb
        from langchain_community.vectorstores import Chroma
        from chromadb.config import Settings
        chroma_client = chromadb.PersistentClient(
            path="./chroma_data",
            settings=Settings(anonymized_telemetry=False)
        )
        return Chroma(
            client=chroma_client,
            collection_name=config["collection_name"],
            embedding_function=embeddings
        )
    elif config["type"] == "qdrant":
        return QdrantVectorStore(
            client=QdrantClient(
                url=config["url"],
                api_key=config["api_key"]
            ),
            collection_name=config["collection_name"],
            embedding=embeddings
        )
    else:
        raise ValueError(f"Unsupported vector store type: {config['type']}")