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
    embed_max_chars: int = 6000
    embed_local_model: str = "BAAI/bge-m3"   # provider=local 时的本地模型（HF 名称）   # 单条输入上限：超长文本截断（LaTeX 密集文本实际 token 远高于字符数）

    # --- 向量库 ---
    vector_backend: str = "auto"  # auto | local | chroma
    chroma_dir: str = "./data/chroma"  # 向量数据目录（local 也放这里）
    chroma_collection: str = "math_chunks"

    # --- 存储 ---
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 50

    # --- 解析与 OCR ---
    ocr_enable: bool = True          # PDF 无文字层时是否自动 OCR
    ocr_engine: str = "rapid"        # rapid（默认，CPU）| none
    ocr_dpi: int = 200
    ocr_max_pages: int = 0           # 0 表示不限
    ocr_formula: str = "auto"        # auto | none | rapid_latex (isolated local ONNX) | pix2tex | api
    ocr_formula_api_url: str = ""    # Mathpix 兼容接口，如 https://api.mathpix.com/v3/text
    ocr_formula_api_key: str = ""

    # --- 多模态（VLM）整页转录：OCR_ENGINE=vlm 时使用 ---
    vlm_api_base: str = ""           # 如 https://dashscope.aliyuncs.com/compatible-mode/v1
    vlm_api_key: str = ""
    vlm_model: str = "qwen-vl-max"
    vlm_timeout: int = 120
    vlm_concurrency: int = 4

    # --- 切分 ---
    chunk_size: int = 600
    chunk_overlap: int = 100

    # ================= B 追加：RAG 引擎 =================
    # --- 大模型（DeepSeek，OpenAI 兼容协议）---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048
    llm_timeout_s: float = 60.0
    # 首 token 超时：超过则退避重试（01 §7 降级表）
    llm_first_token_timeout_s: float = 10.0
    llm_max_retries: int = 2
    # 没配 key 时用它跑通链路/演示（回答为模板拼装，不可答辩）
    mock_llm: bool = False

    # --- 检索 ---
    retrieval_top_k: int = 20       # 单路召回条数（向量 / BM25 各取 top_k）
    rerank_top_n: int = 5           # 送进 Prompt 的片段数
    rrf_k: int = 60                 # RRF 平滑常数
    hybrid_enabled: bool = True     # 关掉即退化为纯向量
    # 低于此值直接拒答（B8）。0.62 由 scripts/calibrate_threshold.py 在 bge-m3 上实测标定：
    # 域外问题 top_score 0.48–0.57，正样本 0.51–1.00，取 p90/p10 中点。
    # 注意：dev 哈希向量的分数分布不同（域外可低至 0），换 EMBED_PROVIDER 后必须重标。
    relevance_threshold: float = 0.62
    bm25_cache_ttl_s: int = 60      # BM25 内存索引缓存时间

    # --- 多轮上下文（B9）---
    history_turns: int = 3
    history_char_budget: int = 1500

    # --- Rerank（B7）---
    # provider=local：本地 bge-reranker-v2-m3（断网可用，默认，零外部依赖）
    # provider=api：OpenAI 兼容 /rerank（SiliconFlow 等），需 rerank_api_base/key
    # provider=none：no-op，按 RRF 顺序截断
    rerank_provider: str = "local"
    rerank_local_model: str = "data/models/bge-reranker-v2-m3"
    rerank_api_base: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_timeout_s: float = 15.0

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
