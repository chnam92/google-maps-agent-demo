#!/bin/bash
# 맛집 파인더 데모 — 에이전트(10002)와 웹(5173)을 함께 실행
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "❌ .env 파일이 없습니다. .env.example을 복사해 키를 채워주세요:"
  echo "   cp .env.example .env"
  exit 1
fi

trap 'kill 0' EXIT

echo "▶ 에이전트 서버 시작 (http://localhost:10002)"
(cd agent && uv run . ) &

echo "▶ 웹 개발 서버 시작 (http://localhost:5173)"
(cd web && pnpm dev) &

wait
