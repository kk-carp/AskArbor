"""集中读取环境配置（.env）；其它模块通过 settings 取值，不得直接 os.getenv。"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "change-me-for-local-dev"
DEFAULT_DEMO_PASSWORD = "demo1234"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # local=本机/上课（可写演示账号）；prod=正式（禁默认密钥与演示密码，不写演示账号）
    app_env: str = "local"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fde"

    chat_base_url: str = "https://api.deepseek.com"
    chat_api_key: str = ""
    chat_model: str = "deepseek-chat"

    embed_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embed_batch_size: int = 8

    retrieve_top_k: int = 5
    retrieve_min_score: float = 0.5
    # 混合检索 + 重排（默认双开；关 rerank 时仍用 retrieve_min_score 门控 dense 分）
    retrieve_use_hybrid: bool = True
    retrieve_use_rerank: bool = True
    retrieve_candidate_k: int = 20
    retrieve_rrf_k: int = 60
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidates: int = 20
    rerank_min_score: float = 0.0

    upload_dir: str = "data/uploads"
    # 课件 PPTX 常带图片，10 MB 不够；仍可用 MAX_UPLOAD_BYTES 覆盖
    max_upload_bytes: int = 50 * 1024 * 1024

    chunk_size: int = 800
    chunk_overlap: int = 100
    max_code_member_bytes: int = 512 * 1024

    secret_key: str = DEFAULT_SECRET_KEY
    demo_password: str = DEFAULT_DEMO_PASSWORD
    session_cookie_name: str = "fde_session"

    # 进程内限流：登录按用户名+IP，问答按登录用户
    login_rate_max: int = 20
    login_rate_window_seconds: int = 60
    ask_rate_max: int = 60
    ask_rate_window_seconds: int = 60

    # 生成阶段注入的最近完整轮数（每轮 = 用户 + 助手）；检索仍只用本轮问题
    conversation_history_turns: int = 3

    # 课外搜索 / 薄弱点归纳（进阶资料推荐等学伴能力共用）
    learning_path_search_timeout_seconds: float = 15.0
    learning_path_recent_questions: int = 20
    learning_path_block_keywords: str = ""
    learning_path_block_hosts: str = ""
    tavily_api_key: str = ""

    # 图片识文：Qwen-VL（DashScope OpenAI 兼容）优先，PaddleOCR 兜底
    vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vision_api_key: str = ""
    vision_model: str = "qwen-vl-plus"
    vision_timeout_seconds: float = 60.0
    ocr_enabled: bool = True

    # 进阶资料推荐（旁路 Agent：白名单工具 + 相关性判定/改写）
    advanced_resources_max_steps: int = 16
    advanced_resources_max_refine: int = 1
    advanced_resources_max_topics: int = 3
    advanced_resources_judge_fallback_k: int = 2
    advanced_resources_use_llm_router: bool = False

    @field_validator("app_env")
    @classmethod
    def _normalize_app_env(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"local", "prod"}:
            raise ValueError("APP_ENV 只能是 local 或 prod")
        return normalized


settings = Settings()


def is_local_env() -> bool:
    return settings.app_env == "local"


def is_prod_env() -> bool:
    return settings.app_env == "prod"


def session_https_only() -> bool:
    """正式环境要求登录 Cookie 只走 HTTPS；本机 http 开发保持可发送。"""
    return is_prod_env()


def assert_safe_for_environment() -> None:
    """正式环境拒绝默认密钥/演示密码，避免把上课配置直接拿去对外用。"""
    if not is_prod_env():
        return
    if not settings.secret_key or settings.secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError("正式环境禁止使用默认 SECRET_KEY，请改成随机字符串。")
    if not settings.demo_password or settings.demo_password == DEFAULT_DEMO_PASSWORD:
        raise RuntimeError("正式环境禁止使用默认 DEMO_PASSWORD。")
