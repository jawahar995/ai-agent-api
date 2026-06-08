from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

load_dotenv()


class Config(BaseSettings):
    database_url: str = os.getenv("MONGODB_URI", os.getenv("DATABASE_URL", "mongodb://localhost:27017"))
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "livekit_agent")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "default_api_key")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "default_api_secret")
    livekit_server_url: str = os.getenv("LIVEKIT_SERVER_URL", os.getenv("LIVEKIT_URL", "http://localhost:7880"))
    jwt_secret: str = os.getenv('JWT_SECRET', "47e488e5edf88fc7250bf158801876a0c4d176372f71e17fd1f017e6abccff51")
    
    vector_store_type: str = os.getenv("VECTOR_STORE_TYPE", "qdrant")
    vector_store_url: str = os.getenv("VECTOR_STORE_URL", "localhost")
    vector_store_port: int = int(os.getenv("VECTOR_STORE_PORT", "6333"))
    vector_store_api_key: str = os.getenv("QDRANT_API_KEY", "a91bdca50df5ba016c6ba1d02a4f72bd823defe4fb0b9af3b0e5a260e059c55d")


config = Config()