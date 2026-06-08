from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def configure_embedding(embedding_type, embedding_model, api_key):
    if embedding_type == "openai":
        return OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=api_key
        )
    elif embedding_type == "google_genai":
        return GoogleGenerativeAIEmbeddings(
            model=embedding_model,
            google_api_key=api_key
        )
    else:
        raise Exception(f"Unsupported embedding type: {embedding_type}")