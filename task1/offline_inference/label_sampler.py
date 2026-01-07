# 对采样数据进行Qwen2.5试打标
# 需在vllm服务已启动（端口8000）下运行
import requests
import json
from tqdm import tqdm
import tiktoken
import asyncio
import aiohttp
import re
import os
import sys
from tqdm.asyncio import tqdm_asyncio

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(BASE_DIR, "../sample_2000.jsonl")
RESULT_PATH = os.path.join(BASE_DIR, "../sample_2000_labeled.jsonl")

API_URL = "http://localhost:8000/v1/chat/completions"

# 导入提示模板
sys.path.append(BASE_DIR)
from prompt_templates import CATEGORY_PROMPT

import string
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT.replace("{", "{{").replace("}", "}}")
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT_SAFE.replace("{{content}}", "{content}")

def truncate_content(content, max_tokens=3500):
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(content)
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
    return enc.decode(tokens, errors="ignore")

def clean_markdown_json(text):
    """去除Markdown代码块标记，提取JSON内容"""
    text = text.strip()
    # 匹配 ```json ... ``` 或 ``` ... ```
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
    if match:
        return match.group(1)
    return text

async def async_get_qwen_label(session, content, semaphore):
    async with semaphore:
        # 动态计算max_tokens，保证总tokens不超过4096
        enc = tiktoken.get_encoding("cl100k_base")
        truncated_content = truncate_content(content)
        input_tokens = len(enc.encode(truncated_content))
        # 预留给生成的tokens，至少128，最多512
        max_tokens = max(128, min(4096 - input_tokens - 200, 512))
        
        payload = {
            "model": "/home/jiamin/Qwen/Qwen2.5-7B-Instruct",
            "messages": [
                {"role": "system", "content": "你是一个场景分类与数据增强专家。"},
                {"role": "user", "content": CATEGORY_PROMPT_SAFE.format(content=truncated_content)}
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens
        }
        try:
            async with session.post(API_URL, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                resp.raise_for_status()
                result = await resp.json()
                raw_content = result["choices"][0]["message"]["content"]
                return clean_markdown_json(raw_content)
        except Exception as e:
            # 记录更详细的错误
            return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})

async def main_async():
    # 限制并发数为 30
    sem = asyncio.Semaphore(30)
    
    tasks = []
    with open(SAMPLE_PATH, "r", encoding="utf-8") as fin:
        lines = fin.readlines()
        
    print(f"Loaded {len(lines)} lines. Starting labeling...")
    
    async with aiohttp.ClientSession() as session:
        for line in lines:
            item = json.loads(line)
            content = item.get("content", "")
            tasks.append(async_get_qwen_label(session, content, sem))
            
        results = []
        # 使用tqdm显示进度
        for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Qwen标注中"):
            result = await coro
            results.append(result)
            
    with open(RESULT_PATH, "w", encoding="utf-8") as fout:
        for line, label in zip(lines, results):
            item = json.loads(line)
            item["qwen_label"] = label
            fout.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    print(f"Finished. Results saved to {RESULT_PATH}")

if __name__ == "__main__":
    asyncio.run(main_async())
