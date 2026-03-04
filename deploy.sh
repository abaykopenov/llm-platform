#!/bin/bash
# ============================================================
#  LLM Platform — One-Click Server Deploy
# ============================================================
#  Загрузите проект на сервер и запустите:
#    chmod +x deploy.sh && ./deploy.sh
#
#  Скрипт автоматически:
#  1. Проверит/установит Docker и Docker Compose
#  2. Соберёт web-ui (если нужен npm build)
#  3. Запустит все сервисы через docker-compose
#  4. Подождёт пока Ollama запустится
#  5. Автоматически скачает embedding-модель
#  6. Покажет все доступные модели
# ============================================================

set -e

# ─── Colors ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║        ⚡ LLM Platform — Server Deploy           ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Step 1: Check Docker ──────────────────────────────────
echo -e "${BLUE}[1/7]${NC} Проверка Docker..."

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}  Docker не найден. Устанавливаю...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo -e "${GREEN}  ✅ Docker установлен${NC}"
    echo -e "${YELLOW}  ⚠️  Если это первый запуск, возможно нужно перелогиниться для docker без sudo${NC}"
else
    echo -e "${GREEN}  ✅ Docker: $(docker --version | head -c 50)${NC}"
fi

# Check docker compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}  ✅ Docker Compose: $(docker compose version --short 2>/dev/null || echo 'OK')${NC}"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo -e "${GREEN}  ✅ Docker Compose (legacy): $(docker-compose --version | head -c 50)${NC}"
else
    echo -e "${YELLOW}  Docker Compose не найден. Устанавливаю...${NC}"
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin 2>/dev/null || \
    sudo yum install -y docker-compose-plugin 2>/dev/null || \
    pip3 install docker-compose 2>/dev/null
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}  ✅ Docker Compose установлен${NC}"
fi

# ─── Step 2: Create .env if missing ───────────────────────
echo -e "${BLUE}[2/7]${NC} Проверка конфигурации..."

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}  Создаю .env с настройками по умолчанию...${NC}"
    cat > .env << 'ENVEOF'
# ============================================================
#  LLM Platform — Environment Configuration
# ============================================================

# --- Inference URL ---
# Используется Ollama в Docker-контейнере (сервис ollama)
INFERENCE_URL=http://ollama:11434

# --- Service Ports ---
GATEWAY_PORT=8000
RAG_ENGINE_PORT=8200
CHROMADB_PORT=8400
WEBUI_PORT=3001
OLLAMA_PORT=11434

# --- RAG ---
EMBEDDING_MODEL=nomic-embed-text
CHUNK_SIZE=800
CHUNK_OVERLAP=100
DEFAULT_COLLECTION=general

# --- Auth (optional) ---
# API_KEYS=key1,key2,key3

# --- Rate Limiting ---
RATE_LIMIT_RPM=60

# --- Default models to pull on startup ---
# Через запятую. Embedding-модель подтягивается автоматически.
AUTO_PULL_MODELS=gemma3:4b
ENVEOF
    echo -e "${GREEN}  ✅ .env создан${NC}"
else
    echo -e "${GREEN}  ✅ .env уже существует${NC}"
    # Ensure INFERENCE_URL points to docker ollama
    if grep -q "host.docker.internal" .env; then
        echo -e "${YELLOW}  ⚠️  Меняю INFERENCE_URL на Docker-контейнер Ollama...${NC}"
        sed -i 's|INFERENCE_URL=http://host.docker.internal:11434|INFERENCE_URL=http://ollama:11434|g' .env
    fi
fi

# Source .env
set -a
source .env
set +a

# ─── Step 3: Check NVIDIA GPU ─────────────────────────────
echo -e "${BLUE}[3/7]${NC} Проверка GPU..."

GPU_AVAILABLE=false
NVIDIA_RUNTIME=""

if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "")
    if [ -n "$GPU_INFO" ]; then
        GPU_AVAILABLE=true
        echo -e "${GREEN}  ✅ GPU обнаружен: ${GPU_INFO}${NC}"
        
        # Check NVIDIA Container Toolkit
        if docker info 2>/dev/null | grep -q "nvidia"; then
            NVIDIA_RUNTIME="--gpus all"
            echo -e "${GREEN}  ✅ NVIDIA Container Toolkit установлен${NC}"
        else
            echo -e "${YELLOW}  ⚠️  NVIDIA Container Toolkit не установлен.${NC}"
            echo -e "${YELLOW}     Ollama будет работать на CPU. Для GPU:${NC}"
            echo -e "${YELLOW}     https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html${NC}"
        fi
    fi
else
    echo -e "${YELLOW}  ℹ️  GPU не обнаружен — Ollama будет на CPU${NC}"
fi

# ─── Step 4: Build web-ui ─────────────────────────────────
echo -e "${BLUE}[4/7]${NC} Сборка Web UI..."

# Determine server IP for NEXT_PUBLIC_API_URL
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
GATEWAY_PORT="${GATEWAY_PORT:-8000}"

if [ -d "web-ui/.next/standalone" ]; then
    echo -e "${GREEN}  ✅ Web UI уже собран (standalone)${NC}"
else
    echo -e "${YELLOW}  Собираю Web UI...${NC}"
    
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        cd web-ui
        export NEXT_PUBLIC_API_URL="http://${SERVER_IP}:${GATEWAY_PORT}"
        echo -e "  API URL: ${NEXT_PUBLIC_API_URL}"
        npm install --legacy-peer-deps 2>/dev/null || npm install
        npm run build
        cd "$SCRIPT_DIR"
        echo -e "${GREEN}  ✅ Web UI собран${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Node.js не найден. Собираю через Docker...${NC}"
        docker run --rm \
            -v "$SCRIPT_DIR/web-ui:/app" \
            -w /app \
            -e NEXT_PUBLIC_API_URL="http://${SERVER_IP}:${GATEWAY_PORT}" \
            node:20-alpine sh -c "npm install --legacy-peer-deps && npm run build"
        echo -e "${GREEN}  ✅ Web UI собран через Docker${NC}"
    fi
fi

# ─── Step 5: Start all services ───────────────────────────
echo -e "${BLUE}[5/7]${NC} Запуск всех сервисов..."

$COMPOSE_CMD down 2>/dev/null || true

# Select correct compose file based on GPU availability
if [ "$GPU_AVAILABLE" = true ] && docker info 2>/dev/null | grep -q "nvidia"; then
    echo -e "  🎮 Используется GPU-конфигурация"
    $COMPOSE_CMD up -d --build
else
    echo -e "  💻 Используется CPU-конфигурация"
    $COMPOSE_CMD -f docker-compose.cpu.yml up -d --build
fi

echo -e "${GREEN}  ✅ Сервисы запущены${NC}"

# ─── Step 6: Wait for Ollama and pull models ──────────────
echo -e "${BLUE}[6/7]${NC} Ожидание запуска Ollama..."

OLLAMA_PORT_HOST="${OLLAMA_PORT:-11434}"
OLLAMA_URL="http://localhost:${OLLAMA_PORT_HOST}"

# Wait up to 60 seconds for Ollama to start
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Ollama запущена${NC}"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -ne "\r  ⏳ Ожидание... ${WAITED}с"
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}  ⚠️ Ollama не отвечает через ${MAX_WAIT}с, но продолжаем...${NC}"
fi

# Pull embedding model (required for RAG)
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"
echo -e "  📦 Загрузка embedding-модели: ${EMBEDDING_MODEL}..."
$COMPOSE_CMD exec -T ollama ollama pull "$EMBEDDING_MODEL" 2>/dev/null && \
    echo -e "${GREEN}  ✅ ${EMBEDDING_MODEL} загружена${NC}" || \
    echo -e "${YELLOW}  ⚠️  Не удалось загрузить ${EMBEDDING_MODEL} — загрузите позже через UI${NC}"

# Pull default models
AUTO_PULL_MODELS="${AUTO_PULL_MODELS:-}"
if [ -n "$AUTO_PULL_MODELS" ]; then
    IFS=',' read -ra MODELS_TO_PULL <<< "$AUTO_PULL_MODELS"
    for model in "${MODELS_TO_PULL[@]}"; do
        model=$(echo "$model" | xargs) # trim whitespace
        echo -e "  📦 Загрузка модели: ${model}..."
        $COMPOSE_CMD exec -T ollama ollama pull "$model" 2>/dev/null && \
            echo -e "${GREEN}  ✅ ${model} загружена${NC}" || \
            echo -e "${YELLOW}  ⚠️  Не удалось загрузить ${model}${NC}"
    done
fi

# ─── Step 7: Show status ─────────────────────────────────
echo -e "${BLUE}[7/7]${NC} Проверка статуса..."
echo ""

# Get available models
echo -e "${CYAN}${BOLD}  📦 Доступные модели:${NC}"
MODELS_JSON=$(curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null || echo '{"models":[]}')
echo "$MODELS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    if not models:
        print('     (нет моделей)')
    for m in models:
        name = m.get('name', '?')
        size_gb = round(m.get('size', 0) / (1024**3), 1)
        family = m.get('details', {}).get('family', '')
        params = m.get('details', {}).get('parameter_size', '')
        quant = m.get('details', {}).get('quantization_level', '')
        info_parts = [f for f in [params, family, quant] if f]
        info = ' · '.join(info_parts)
        print(f'     🤖 {name}  ({size_gb} GB)  {info}')
except:
    print('     (не удалось получить список моделей)')
" 2>/dev/null || echo "     (Python3 не доступен для отображения)"

# Final output
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
WEBUI_PORT="${WEBUI_PORT:-3001}"

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║           ✅ Платформа запущена!                  ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}🌐 Web UI:${NC}       http://${SERVER_IP}:${WEBUI_PORT}"
echo -e "  ${BOLD}🔌 API Gateway:${NC}  http://${SERVER_IP}:${GATEWAY_PORT}"
echo -e "  ${BOLD}📚 API Docs:${NC}     http://${SERVER_IP}:${GATEWAY_PORT}/docs"
echo -e "  ${BOLD}🦙 Ollama:${NC}       http://${SERVER_IP}:${OLLAMA_PORT_HOST}"
echo -e "  ${BOLD}🏥 Health:${NC}       http://${SERVER_IP}:${GATEWAY_PORT}/health"
echo ""
echo -e "  ${CYAN}Управление:${NC}"
echo -e "    Логи:        ${COMPOSE_CMD} logs -f"  
echo -e "    Стоп:        ${COMPOSE_CMD} down"
echo -e "    Рестарт:     ${COMPOSE_CMD} restart"
echo -e "    Добавить модель: ${COMPOSE_CMD} exec ollama ollama pull <model>"
echo ""
echo -e "  ${CYAN}Модели можно загружать через Web UI → вкладка \"Модели\"${NC}"
echo ""
