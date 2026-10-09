FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# Use CPU wheels so Docker works on machines without a GPU or CUDA runtime.
RUN python -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir .

ENV HF_HOME=/models
WORKDIR /workspace
ENTRYPOINT ["brain"]
