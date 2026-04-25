FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 (lxml 빌드 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libxml2-dev libxslt-dev tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo "Asia/Seoul" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul

# 의존성 설치 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 서버 전용 requirements (데스크톱 UI 제외)
RUN pip uninstall -y pywebview pystray Pillow 2>/dev/null || true

# 소스 복사 — v7.5(screener/) + Axis(api/agents/personas/utils/data/)
COPY screener/ screener/
COPY api/ api/
COPY agents/ agents/
COPY personas/ personas/
COPY utils/ utils/
COPY data/ data/

# 환경 변수 기본값
ENV RUN_MODE=server
ENV PORT=8501
# readonly: Firestore 읽기만 (크롤링은 collector.py가 별도 수행)
# full: 크롤링 + Firestore 쓰기 (로컬 개발용)
ENV COLLECT_MODE=readonly

EXPOSE ${PORT}

CMD uvicorn screener.main:app --host 0.0.0.0 --port ${PORT}
