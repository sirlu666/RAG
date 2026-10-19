"""测试环境：在导入 app 之前把数据目录切到临时路径，避免污染 data/。"""

import os
import shutil
from pathlib import Path

TMP = Path(__file__).resolve().parent / ".pytest_data"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TMP / "uploads")
os.environ["CHROMA_DIR"] = str(TMP / "chroma")
os.environ["EMBED_PROVIDER"] = "dev"
os.environ["VECTOR_BACKEND"] = "local"
os.environ["APP_ENV"] = "test"
