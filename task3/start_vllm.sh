#!/bin/bash

# Configuration
MODEL_PATH="/home/jiamin/Qwen/Qwen2.5-7B-Instruct"
PORT=8000
GPU_MEMORY_UTILIZATION=0.6
MAX_MODEL_LEN=4096

echo "Starting vLLM server..."
echo "Model: $MODEL_PATH"
echo "Port: $PORT"

# Use python -m vllm.entrypoints.openai.api_server
# Auto-detect tensor parallelism (will likely use 2 GPUs if available)
python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$MODEL_PATH" \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-model-len "$MAX_MODEL_LEN" \
    --trust-remote-code \
    --tensor-parallel-size 2
