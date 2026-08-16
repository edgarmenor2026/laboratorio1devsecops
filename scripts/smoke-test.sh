#!/usr/bin/env sh
set -eu

BASE_URL="${1:-http://127.0.0.1:7860}"

curl -fsS "${BASE_URL}/health/ready"
printf '\n'
curl -fsS -X POST "${BASE_URL}/api/analizar" \
  -H 'Content-Type: application/json' \
  -d '{"texto":"Tengo un cobro injusto de Bancolombia y necesito corregir mi reporte."}'
printf '\n'
