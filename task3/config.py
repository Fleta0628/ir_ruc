import os
import torch

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Model Paths
# LLM Path (Local path for vLLM server to load)
LLM_MODEL_PATH = "/home/jiamin/Qwen/Qwen2.5-7B-Instruct"
# Embedding Path from Task 2
EMBEDDING_MODEL_PATH = "/home/jiamin/RuC_courses/assignment1/work3/models/bge-m3"

# API Configuration (New)
LLM_API_URL = "http://localhost:8000/v1"
LLM_API_KEY = "EMPTY" # Local vLLM typically doesn't require a key
LLM_MODEL_NAME = LLM_MODEL_PATH # vLLM uses the path as the model name by default

# Data Paths
CHROMA_DB_DIR = os.path.join(ROOT_DIR, "task2/chroma_db")
ENRICHED_DATA_PATH = os.path.join(ROOT_DIR, "processed_data/enriched_data.jsonl")
BM25_INDEX_PATH = os.path.join(BASE_DIR, "bm25_index.pkl")

# Device Configuration
# GPU 0: Embedding & Vector Search (In-process)
# GPU 1: LLM Router (Managed by external vLLM service)
if torch.cuda.is_available():
    DEVICE_EMBEDDING = "cuda:0"
else:
    DEVICE_EMBEDDING = "cpu"

# Retrieval Config
TOP_K_VECTOR = 50
TOP_K_BM25 = 50

print(f"[Config] Embedding Device: {DEVICE_EMBEDDING}")
print(f"[Config] LLM API: {LLM_API_URL}")
