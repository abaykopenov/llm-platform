#!/bin/bash
# ============================================================
#  vLLM Inference — Startup Script
# ============================================================
#  Launches vLLM OpenAI-compatible server with the configured model.
#  Environment variables override defaults from config.yaml.
# ============================================================

set -e

MODEL_PATH="${MODEL_PATH:-/models/Qwen2.5-72B-Instruct-AWQ}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-2}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"
PORT="${PORT:-8300}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"

echo "============================================================"
echo "  🤖 vLLM Inference Server"
echo "============================================================"
echo "  Model:    ${MODEL_PATH}"
echo "  TP Size:  ${TENSOR_PARALLEL_SIZE}"
echo "  GPU Mem:  ${GPU_MEMORY_UTILIZATION}"
echo "  Max Len:  ${MAX_MODEL_LEN}"
echo "  Port:     ${PORT}"
echo "============================================================"

# Check if model exists
if [ ! -d "${MODEL_PATH}" ] && [ ! -f "${MODEL_PATH}" ]; then
    echo "⚠️  WARNING: Model path '${MODEL_PATH}' not found!"
    echo "  Make sure NFS volume is mounted correctly."
    echo "  Waiting 10s before attempting to start..."
    sleep 10
fi

exec python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_PATH}" \
    --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
    --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
    --max-model-len "${MAX_MODEL_LEN}" \
    --max-num-seqs "${MAX_NUM_SEQS}" \
    --host "0.0.0.0" \
    --port "${PORT}" \
    --trust-remote-code \
    --dtype auto
