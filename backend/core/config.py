from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "LandRight API"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # Database
    database_url: str

    # Groq
    groq_api_key: str = ""

    # AWS (S3 + SES only — LLM is now Groq)
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "landright-knowledge"
    ses_from_email: str = ""

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    collection_name: str = "landright_docs"

    # LangSmith
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "landright"

    class Config:
        env_file = ".env"


settings = Settings()
