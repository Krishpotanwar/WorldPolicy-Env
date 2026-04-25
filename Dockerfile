FROM python:3.11-slim

# HF Spaces expects port 7860
ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-train the PyTorch StabilityScorer at build time so scorer_weights.pt is
# baked into the image. Trains in <30s on the build runner; saves a runtime
# cold-start cost and ensures the env is deterministic from the first /reset.
RUN python pytorch_scorer.py

# V16 (3_antigravityLOG.md): non-root user for security best practice.
RUN adduser --disabled-password --gecos "" --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

CMD ["python", "server.py"]
