FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    zsh \
    fish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY acp.py .
COPY tests/completions/test_completions.sh .

RUN chmod +x test_completions.sh

CMD ["./test_completions.sh"]
