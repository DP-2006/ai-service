from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OLLAMA_HOST: str = "http://localhost:11434"
    MODEL_TEXT: str = "gemma3:27b"
    MODEL_VISION: str = "gemma3:27b"
    MODEL_EMBED: str = "nomic-embed-text"

    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION: str = "org_knowledge"

    WEBHOOK_SECRET: str = "dev-secret"
    WEBHOOK_MAX_AGE_SECONDS: int = 300

    ADMIN_ALERT_URL: str = ""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9000
    LOG_LEVEL: str = "INFO"


settings = Settings(
    OLLAMA_HOST="http://localhost:11434",
    CHROMA_HOST="localhost",
    CHROMA_PORT=8001,
    MODEL_TEXT="gemma3:27b",
    MODEL_VISION="gemma3:27b",
    MODEL_EMBED="nomic-embed-text",
)
