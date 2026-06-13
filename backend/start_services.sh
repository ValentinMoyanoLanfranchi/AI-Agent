#!/usr/bin/env bash
#
# start_services.sh — Levanta el backend (FastAPI) del Sistema de Agentes IA.
#
# Setup actual: base de datos en Supabase + Celery en modo eager (sin Redis).
# No requiere Docker, PostgreSQL ni Redis locales.
#
# Uso:
#   ./start_services.sh                  # instala deps, migra tablas y levanta uvicorn
#   ./start_services.sh --no-install     # salta el pip install (arranque rápido)
#   ./start_services.sh --no-migrate     # salta init_db.py
#   ./start_services.sh --seed           # además dispara la ingesta inicial al arrancar
#   ./start_services.sh --reload         # uvicorn con auto-reload (desarrollo)
#
# Variables de entorno opcionales:
#   HOST=0.0.0.0 PORT=8080 PYTHON=python3 ./start_services.sh
#
set -euo pipefail

# El script vive en backend/. La raíz del repo (donde está .env) es un nivel arriba.
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python}"

INSTALL=1
MIGRATE=1
SEED=0
RELOAD=0

for arg in "$@"; do
  case "$arg" in
    --no-install) INSTALL=0 ;;
    --no-migrate) MIGRATE=0 ;;
    --seed)       SEED=1 ;;
    --reload)     RELOAD=1 ;;
    -h|--help)    awk 'NR>1 && !/^#/{exit} NR>1{sub(/^# ?/,""); print}' "$0"; exit 0 ;;
    *) echo "❌ Argumento desconocido: $arg (usá --help)"; exit 1 ;;
  esac
done

echo ""
echo "============================================================"
echo "  🛰️  Sistema de Agentes IA — backend"
echo "============================================================"

# ── 1. Verificar .env ─────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
    echo "⚠️  No existe .env — copiando desde .env.example. Editalo antes de usar en serio."
    cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
  else
    echo "❌ No existe .env ni .env.example en $PROJECT_ROOT"; exit 1
  fi
fi

# Solo mirar líneas reales (no comentarios) de DATABASE_URL para no dar falsos
# positivos con el texto de ayuda que menciona [TU-PASSWORD].
if grep -E '^\s*DATABASE_URL' "$ENV_FILE" | grep -q "TU-PASSWORD"; then
  echo "❌ El .env todavía tiene el placeholder [TU-PASSWORD] en DATABASE_URL."
  echo "   Completá la contraseña de Supabase antes de arrancar."
  exit 1
fi
if grep -qE "OPENAI_API_KEY=(sk-your|sk-REEMPLAZAR|$)" "$ENV_FILE" 2>/dev/null; then
  echo "⚠️  OPENAI_API_KEY no configurada: el backend levanta, pero los agentes"
  echo "    (POST /api/agents/*) no podrán generar reportes."
fi

cd "$BACKEND_DIR"

# ── 2. Activar venv si existe ─────────────────────────────────
for venv in "$BACKEND_DIR/.venv" "$PROJECT_ROOT/.venv"; do
  if [[ -f "$venv/Scripts/activate" ]]; then source "$venv/Scripts/activate"; echo "🐍 venv: $venv"; break
  elif [[ -f "$venv/bin/activate" ]]; then source "$venv/bin/activate"; echo "🐍 venv: $venv"; break; fi
done

# ── 3. Instalar dependencias ──────────────────────────────────
if [[ "$INSTALL" -eq 1 ]]; then
  echo "📦 Instalando dependencias (usá --no-install para saltar)..."
  "$PYTHON" -m pip install -r requirements.txt -q
  echo "✅ Dependencias listas"
fi

# ── 4. Migrar tablas (idempotente: crea solo lo que falta) ────
if [[ "$MIGRATE" -eq 1 ]]; then
  echo "🗄️  Verificando/creando tablas en Supabase..."
  "$PYTHON" init_db.py
fi

# ── 5. Levantar backend ───────────────────────────────────────
UVICORN_ARGS=(main:app --host "$HOST" --port "$PORT" --log-level info)
[[ "$RELOAD" -eq 1 ]] && UVICORN_ARGS+=(--reload)

echo ""
echo "🚀 Levantando backend en http://$HOST:$PORT  (docs: /docs)"
echo "============================================================"

if [[ "$SEED" -eq 1 ]]; then
  # Arrancar en background, esperar health, sembrar datos y seguir en foreground.
  "$PYTHON" -m uvicorn "${UVICORN_ARGS[@]}" &
  UVICORN_PID=$!
  trap 'echo ""; echo "🛑 Deteniendo backend..."; kill "$UVICORN_PID" 2>/dev/null || true' INT TERM EXIT

  echo "⏳ Esperando que el backend responda..."
  for i in $(seq 1 30); do
    if curl -s -o /dev/null "http://$HOST:$PORT/health" 2>/dev/null; then
      echo "✅ Backend arriba — disparando ingesta inicial..."
      curl -s -X POST "http://$HOST:$PORT/api/ingest/all" -w "\n   ingest → HTTP %{http_code}\n" || true
      break
    fi
    sleep 2
  done
  wait "$UVICORN_PID"
else
  exec "$PYTHON" -m uvicorn "${UVICORN_ARGS[@]}"
fi
