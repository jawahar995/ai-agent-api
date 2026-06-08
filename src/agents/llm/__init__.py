from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


def create_llm(config: dict):
    
    provider = config["provider"]

    llm_settings = config["llm_settings"]

    if provider == "openai":

        return ChatOpenAI(
            api_key=llm_settings["api_key"],
            model=llm_settings["chat_model"],
            temperature=llm_settings["temperature"],
            streaming=True,
            verbose=True
        )
    elif provider in ("gemini", "gimini"):
        return ChatGoogleGenerativeAI(
            google_api_key=llm_settings["api_key"],
            model=llm_settings["chat_model"],
            temperature=llm_settings["temperature"],
            streaming=True,
            verbose=True    
        )

    raise Exception(f"Unsupported provider: {provider}")