#!/bin/bash
echo "============================================"
echo " 주식 종목탐색기 시작"
echo "============================================"
echo ""
echo "서버 시작 중... (http://localhost:8501)"
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

cd "$(dirname "$0")"
PYTHONUTF8=1 conda run -n quant python -m uvicorn screener.main:app --host 0.0.0.0 --port 8501 --reload
