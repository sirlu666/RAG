"""A 的配置（文档链路）。B/C 的配置项由各自追加，不要写在这里。

相对路径统一相对项目根目录，避免从不同 cwd 启动时数据分裂。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


def resolve(p: str | Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (ROOT_DIR / path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # --- Embedding ---
    # dev：本地哈希向量（零依赖、确定性），只用于跑通链路，检索质量不能用于答辩；
    # api：OpenAI 兼容 /embeddings（bge-m3 等），上线与评估时必须切到它。
    embed_provider: str = "dev"
    embed_model: str = "BAAI/bge-m3"
    embed_api_base: str = ""
    embed_api_key: str = ""
    embed_dim: int = 256
    embed_batch: int = 32

    # --- 向量库 ---
    vector_backend: str = "auto"  # auto | local | chroma
    chroma_dir: str = "./data/chroma"  # 向量数据目录（local 也放这里）
    chroma_collection: str = "math_chunks"

    # --- 存储 ---
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 50

    # --- 切分 ---
    chunk_size: int = 600
    chunk_overlap: int = 100

    @property
    def sqlite_path(self) -> Path:
        return resolve(self.database_url.replace("sqlite:///", "", 1))

    @property
    def upload_path(self) -> Path:
        return resolve(self.upload_dir)

    @property
    def chroma_path(self) -> Path:
        return resolve(self.chroma_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
