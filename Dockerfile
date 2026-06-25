FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV LOCAL_LLM_SETUP_OUTPUT=/workspace/output
VOLUME ["/workspace/output"]

ENTRYPOINT ["local-llm-setup"]
CMD ["tui"]
