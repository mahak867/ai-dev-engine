# APEX Society — container image (Hugging Face Spaces, Render, Fly, any Docker host)
FROM python:3.12-slim

# Public-demo defaults: bind all interfaces on the Spaces port, hold no
# provider keys (visitors bring their own or watch the no-LLM replay).
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APEX_HOST=0.0.0.0 APEX_PORT=7860 APEX_PUBLIC_DEMO=1 APEX_TRUST_PROXY=1 \
    APEX_ALLOWED_HOSTS=localhost,127.0.0.1,.hf.space \
    APEX_ALLOWED_ORIGINS=https://*.hf.space,http://localhost:7860 \
    APEX_FRAME_ANCESTORS=https://huggingface.co \
    APEX_MAX_CONCURRENT_JOBS=2 APEX_RUNS_PER_HOUR=6 \
    APEX_RUNS_DIR=/tmp/apex-runs APEX_MEMORY_DIR=/tmp/apex-memory

# Spaces run containers as uid 1000
RUN useradd -m -u 1000 apex
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=apex:apex . .
USER apex

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/api/health')" || exit 1
CMD ["python", "server.py"]
