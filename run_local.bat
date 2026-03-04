@echo off
REM ============================================================
REM  LLM Platform — Local Test Runner (Windows)
REM  Запускает Gateway + RAG Engine локально без Docker.
REM  Требования: Python 3.10+, локально запущенная Ollama
REM ============================================================

echo.
echo  ===================================
echo  LLM Platform - Local Test Mode
echo  ===================================
echo.

REM --- Проверка Ollama ---
echo [1/5] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Ollama не запущена! Запустите "ollama serve" в отдельном терминале.
    pause
    exit /b 1
)
echo  OK: Ollama работает

REM --- Настройка переменных ---
set INFERENCE_URL=http://localhost:11434
set CHROMADB_URL=http://localhost:8400
set RAG_ENGINE_URL=http://localhost:8200
set EMBEDDING_MODEL=nomic-embed-text
set CHUNK_SIZE=800
set CHUNK_OVERLAP=100
set DEFAULT_COLLECTION=general
set UPLOAD_DIR=%~dp0uploads
set RATE_LIMIT_RPM=60
set API_KEYS=

if not exist "%UPLOAD_DIR%" mkdir "%UPLOAD_DIR%"

REM --- Установка зависимостей Gateway ---
echo.
echo [2/5] Установка зависимостей Gateway...
cd /d "%~dp0gateway"
if not exist "venv" python -m venv venv
call venv\Scripts\activate
pip install -q -r requirements.txt 2>nul

REM --- Установка зависимостей RAG Engine ---
echo.
echo [3/5] Установка зависимостей RAG Engine...
cd /d "%~dp0rag-engine"
if not exist "venv" python -m venv venv
call venv\Scripts\activate
pip install -q -r requirements.txt 2>nul

REM --- Запуск RAG Engine (фоном) ---
echo.
echo [4/5] Запуск RAG Engine на :8200 ...
cd /d "%~dp0rag-engine"
call venv\Scripts\activate
start /B "RAG Engine" cmd /c "python -m uvicorn main:app --host 0.0.0.0 --port 8200"

REM Ждём немного
timeout /t 3 /nobreak >nul

REM --- Запуск Gateway ---
echo.
echo [5/5] Запуск Gateway на :8000 ...
echo.
echo  ===================================
echo  Platform is running!
echo  Gateway:    http://localhost:8000
echo  RAG Engine: http://localhost:8200
echo  Ollama:     http://localhost:11434
echo  ===================================
echo.
echo  API:   http://localhost:8000/v1/chat/completions
echo  Docs:  http://localhost:8000/docs
echo  Health: http://localhost:8000/health
echo.

cd /d "%~dp0gateway"
call venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
