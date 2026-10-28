FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r backend/requirements.txt
COPY backend/requirements-formula.txt /app/backend/requirements-formula.txt
RUN python -m venv /opt/formula && /opt/formula/bin/pip install -r backend/requirements-formula.txt
ENV OCR_FORMULA=rapid_latex FORMULA_PYTHON=/opt/formula/bin/python FORMULA_MODEL_DIR=/models/formula-onnx
COPY backend/app /app/backend/app
COPY deploy/run.py /app/deploy/run.py
COPY deploy/sample-materials /app/deploy/sample-materials
COPY scripts/formula-worker.py /app/scripts/formula-worker.py
COPY --from=frontend /build/dist /app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30m CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4)"
CMD ["python", "deploy/run.py", "--download-models", "--data-dir", "/data", "--models-dir", "/models", "--host", "0.0.0.0", "--port", "8000"]
