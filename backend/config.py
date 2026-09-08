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
    max_upload_bytes: int = 10 * 1024 * 1024

    chunk_size: int = 800
    chunk_overlap: int = 100
    max_code_member_bytes: int = 512 * 1024

    secret_key: str = "change-me-for-local-dev"
    demo_password: str = "demo1234"
    session_cookie_name: str = "fde_session"

    # 生成阶段注入的最近完整轮数（每轮 = 用户 + 助手）；检索仍只用本轮问题
    conversation_history_turns: int = 3

    # 学习路径课外搜索：arXiv（无 key）+ Tavily（需 TAVILY_API_KEY）；结果再过主机白名单
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
    advanced_resources_max_steps: int = 12
    advanced_resources_max_refine: int = 1
    advanced_resources_max_topics: int = 3
    advanced_resources_judge_fallback_k: int = 2
    advanced_resources_use_llm_router: bool = False


settings = Settings()
