# ⚡ LLM Platform

Универсальная платформа для работы с LLM моделями — чат, RAG (загрузка документов), управление моделями и мониторинг сервера.

## 🚀 Быстрый старт (One-Click Deploy)

Загрузите проект на сервер и выполните одну команду:

```bash
chmod +x deploy.sh && ./deploy.sh
```

**Всё!** Скрипт автоматически:
- ✅ Проверит и установит Docker (если нужно)
- ✅ Определит GPU (NVIDIA) и выберет конфигурацию
- ✅ Соберёт Web UI
- ✅ Запустит все сервисы (Ollama, Gateway, RAG, ChromaDB, Web UI)
- ✅ Скачает embedding-модель для RAG
- ✅ Скачает стартовую LLM-модель
- ✅ Покажет все доступные модели и ссылки

## 📦 Что входит

| Сервис | Порт | Описание |
|--------|------|----------|
| 🌐 **Web UI** | 3001 | Веб-интерфейс: чат, файлы, модели, мониторинг |
| 🔌 **API Gateway** | 8000 | OpenAI-совместимый API |
| 🦙 **Ollama** | 11434 | LLM движок (GPU/CPU) |
| 📚 **RAG Engine** | 8200 | Поиск по документам |
| 🗄️ **ChromaDB** | 8400 | Векторная база данных |

## ⚙️ Настройка

Отредактируйте `.env` перед запуском:

```env
# Какие модели скачать автоматически (через запятую)
AUTO_PULL_MODELS=gemma3:4b

# Порты сервисов
GATEWAY_PORT=8000
WEBUI_PORT=3001
OLLAMA_PORT=11434
```

## 🤖 Управление моделями

### Через Web UI
Откройте `http://ваш-сервер:3001` → вкладка **"Модели"** → загрузите любую модель.

### Через консоль
```bash
# Скачать модель
docker compose exec ollama ollama pull qwen2.5:7b

# Посмотреть установленные
docker compose exec ollama ollama list

# Удалить модель
docker compose exec ollama ollama rm model-name
```

## 📋 Управление платформой

```bash
# Посмотреть логи
docker compose logs -f

# Перезапустить
docker compose restart

# Остановить
docker compose down

# Перезапустить с пересборкой
./deploy.sh
```

## 🔌 API (OpenAI-совместимый)

```bash
# Чат
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3:4b",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'

# Список моделей
curl http://localhost:8000/v1/models

# Статус системы
curl http://localhost:8000/health

# Swagger документация
open http://localhost:8000/docs
```

## 📂 Структура проекта

```
llm-platform/
├── deploy.sh                    # ← ЗАПУСТИТЕ ЭТОТ ФАЙЛ
├── docker-compose.yml           # GPU-конфигурация
├── docker-compose.cpu.yml       # CPU-конфигурация (авто-выбор)
├── .env                         # Настройки
├── gateway/                     # API Gateway (FastAPI)
├── rag-engine/                  # RAG движок (ChromaDB + парсинг)
├── web-ui/                      # Web интерфейс (Next.js)
├── inference/                   # vLLM конфиг (для продакшена)
└── monitoring/                  # Grafana + Prometheus (опционально)
```

## 💡 Требования

- **Linux сервер** (Ubuntu 20.04+, CentOS 7+, Debian 10+)
- **Docker** (устанавливается автоматически)
- **RAM**: минимум 8 ГБ (рекомендуется 16+ ГБ)
- **GPU** (опционально): NVIDIA с CUDA для быстрого инференса
