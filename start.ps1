# start.ps1 — Script de arranque completo del sistema
# Uso: .\start.ps1
# Opcional: .\start.ps1 -Mode local  (sin Docker)

param(
    [string]$Mode = "docker"   # "docker" o "local"
)

$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  🛰️  Sistema de Agentes IA — Hackathon Junio 2026" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Verificar .env ────────────────────────────────────────────
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvContent = Get-Content $EnvFile -Raw
if ($EnvContent -match "sk-REEMPLAZAR" -or $EnvContent -match "sk-ant-REEMPLAZAR") {
    Write-Host "⚠️  ADVERTENCIA: Las API Keys de LLM no están configuradas en .env" -ForegroundColor Yellow
    Write-Host "   El sistema levantará, pero los agentes NO podrán generar reportes." -ForegroundColor Yellow
    Write-Host "   Editar .env y reemplazar OPENAI_API_KEY y/o ANTHROPIC_API_KEY" -ForegroundColor Yellow
    Write-Host ""
}

if ($Mode -eq "docker") {
    # ── Modo Docker Compose ───────────────────────────────────

    # Verificar Docker
    Write-Host "🐋 Verificando Docker Desktop..." -ForegroundColor Blue
    $dockerOk = $false
    $attempts = 0
    while (-not $dockerOk -and $attempts -lt 30) {
        $result = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dockerOk = $true
        } else {
            $attempts++
            if ($attempts -eq 1) {
                Write-Host "   Docker Desktop no está corriendo. Iniciándolo..." -ForegroundColor Yellow
                Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
            }
            Write-Host "   Esperando Docker Desktop... ($attempts/30)" -ForegroundColor Gray
            Start-Sleep -Seconds 5
        }
    }

    if (-not $dockerOk) {
        Write-Host "❌ Docker Desktop no pudo iniciarse. Usa -Mode local para ejecutar sin Docker." -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Docker Desktop listo" -ForegroundColor Green

    # Build y levantar servicios
    Write-Host ""
    Write-Host "🏗️  Construyendo y levantando servicios..." -ForegroundColor Blue
    Set-Location $ProjectRoot
    docker compose up --build -d

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error levantando servicios con docker compose" -ForegroundColor Red
        exit 1
    }

    # Esperar que la DB esté healthy
    Write-Host ""
    Write-Host "⏳ Esperando que PostgreSQL esté listo..." -ForegroundColor Blue
    $dbReady = $false
    $dbAttempts = 0
    while (-not $dbReady -and $dbAttempts -lt 24) {
        Start-Sleep -Seconds 5
        $dbAttempts++
        $health = docker inspect hackaton_db --format='{{.State.Health.Status}}' 2>&1
        Write-Host "   DB status: $health ($dbAttempts/24)" -ForegroundColor Gray
        if ($health -eq "healthy") {
            $dbReady = $true
        }
    }

    if (-not $dbReady) {
        Write-Host "⚠️  PostgreSQL tardó más de lo esperado. Verificar logs: docker logs hackaton_db" -ForegroundColor Yellow
    } else {
        Write-Host "✅ PostgreSQL listo" -ForegroundColor Green
    }

    # Seed de datos iniciales
    Write-Host ""
    Write-Host "🌱 Iniciando ingesta de datos (puede tardar 30-60 segundos)..." -ForegroundColor Blue
    Start-Sleep -Seconds 10  # Dar tiempo al backend para arrancar
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/api/ingest/all" -Method POST -TimeoutSec 30
        Write-Host "✅ Ingesta iniciada: $($response.status)" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  No se pudo iniciar la ingesta automáticamente. Hacerlo manualmente:" -ForegroundColor Yellow
        Write-Host "   curl -X POST http://localhost:8000/api/ingest/all" -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✅ Sistema levantado correctamente!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  🌐 Dashboard:    http://localhost:5173" -ForegroundColor Cyan
    Write-Host "  📡 API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "  🏥 Health Check: http://localhost:8000/health" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Ejecutar todos los agentes:" -ForegroundColor Yellow
    Write-Host '  Invoke-RestMethod -Uri "http://localhost:8000/api/agents/run-all" -Method POST -Body ''{"days_back":7}'' -ContentType "application/json"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Ver logs en tiempo real:" -ForegroundColor Yellow
    Write-Host "  docker compose logs -f backend" -ForegroundColor Gray
    Write-Host ""

} elseif ($Mode -eq "local") {
    # ── Modo Local (sin Docker) ───────────────────────────────
    Write-Host "🖥️  Modo: Desarrollo Local (sin Docker)" -ForegroundColor Blue
    Write-Host "   Asegurate de tener PostgreSQL y Redis corriendo localmente." -ForegroundColor Yellow
    Write-Host "   Usar .env.local como .env (apunta a localhost en lugar de 'db')" -ForegroundColor Yellow
    Write-Host ""

    # Instalar dependencias Python
    Write-Host "📦 Verificando dependencias Python..." -ForegroundColor Blue
    Set-Location $BackendDir
    python -m pip install -r requirements.txt -q
    Write-Host "✅ Dependencias instaladas" -ForegroundColor Green

    # Inicializar DB
    Write-Host ""
    Write-Host "🗄️  Inicializando base de datos..." -ForegroundColor Blue
    python init_db.py

    Write-Host ""
    Write-Host "✅ Listo! Levantá los servicios manualmente:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Terminal 1 — Backend:" -ForegroundColor Yellow
    Write-Host "  cd backend && uvicorn main:app --reload" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Terminal 2 — Celery Worker:" -ForegroundColor Yellow
    Write-Host "  cd backend && celery -A ingestion.tasks worker --loglevel=info" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Terminal 3 — Frontend:" -ForegroundColor Yellow
    Write-Host "  cd frontend && npm install && npm run dev" -ForegroundColor Gray
    Write-Host ""
}
