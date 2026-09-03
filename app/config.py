from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fde"

    chat_base_url: str = "https://api.deepseek.com"
    chat_api_key: str = ""
    chat_model: str = "deepseek-chat"

    embed_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embed_batch_size: int = 8

    retrieve_top_k: int = 5
    retrieve_min_score: float = 0.3

    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024

    chunk_size: int = 800
    chunk_overlap: int = 100

    secret_key: str = "change-me-for-local-dev"
    demo_password: str = "demo1234"
    session_cookie_name: str = "fde_session"

    # 生成阶段注入的最近完整轮数（每轮 = 用户 + 助手）；检索仍只用本轮问题
    conversation_history_turns: int = 3

    # 生成阶段带入的最近完整轮数（每轮 = user + assistant）
    conversation_history_turns: int = 3


settings = Settings()
