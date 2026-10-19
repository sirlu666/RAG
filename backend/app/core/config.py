"""全局配置：所有配置项只从这里读，禁止在业务代码里 hardcode。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/ 的上一级），.env 放在根目录
ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 应用 ---
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- 大模型 ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 60
    llm_max_retries: int = 2

    # --- Embedding ---
    embed_provider: str = "api"  # local | api
    embed_model: str = "BAAI/bge-m3"
    embed_api_base: str = ""
    embed_api_key: str = ""
    embed_dim: int = 1024
    embed_batch: int = 32

    # --- Rerank ---
    rerank_enable: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_n: int = 5

    # --- 检索 ---
    chroma_dir: str = "./data/chroma"
    chroma_collection: str = "math_chunks"
    retrieve_vector_k: int = 20
    retrieve_bm25_k: int = 20
    rrf_k: int = 60
    confidence_threshold: float = 0.35

    # --- 存储 ---
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 50

    # --- 切分 ---
    chunk_size: int = 600
    chunk_overlap: int = 100

    # --- 开发辅助 ---
    mock_llm: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
