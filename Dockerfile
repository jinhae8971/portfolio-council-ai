FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# 소스 복사
COPY . .

# 데이터 디렉토리
RUN mkdir -p data/cache data/history docs/data

# 기본 실행
ENTRYPOINT ["python", "scripts/run_pipeline.py"]
CMD ["--no-notify"]
