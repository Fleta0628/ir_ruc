# vLLM 全量批处理脚本 (流式优化版)
# 用于Task 1: 类别发现与离线数据增强

import os
import json
import asyncio
import aiohttp
import tiktoken
import re
import sys
from tqdm import tqdm

# 路径配置 (相对于脚本所在目录)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "../../crawled_data_deduplicated.jsonl")
PAGERANK_PATH = os.path.join(BASE_DIR, "../../pagerank_results.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "../../processed_data/enriched_data.jsonl")

# 确保输出目录存在
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

# 导入提示模板
sys.path.append(BASE_DIR)
from prompt_templates import CATEGORY_PROMPT

API_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "/home/jiamin/Qwen/Qwen2.5-7B-Instruct"
CONCURRENCY = 120  # 并发数

# 预处理Prompt
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT.replace("{", "{{").replace("}", "}}")
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT_SAFE.replace("{{content}}", "{content}")

def clean_markdown_json(text):
    """去除Markdown代码块标记，提取JSON内容"""
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
    if match:
        return match.group(1)
    return text

def smart_truncate(content, head_tokens=1500, tail_tokens=500):
    """智能截断：保留头尾"""
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        tokens = enc.encode(content)
    except:
        return content[:10000] # Fallback for decoding errors
        
    if len(tokens) <= head_tokens + tail_tokens:
        return content
    
    keep_tokens = tokens[:head_tokens] + tokens[-tail_tokens:]
    return enc.decode(keep_tokens, errors="ignore")

async def fetch_label(session, content):
    truncated = smart_truncate(content)
    enc = tiktoken.get_encoding("cl100k_base")
    input_tokens = len(enc.encode(truncated))
    # 动态计算max_tokens
    max_tokens = max(128, min(4096 - input_tokens - 100, 512))

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个场景分类与数据增强专家。"},
            {"role": "user", "content": CATEGORY_PROMPT_SAFE.format(content=truncated)}
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens
    }
    
    retries = 3
    for attempt in range(retries):
        try:
            async with session.post(API_URL, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    raw = result["choices"][0]["message"]["content"]
                    return clean_markdown_json(raw)
                elif resp.status == 429: # Rate limit
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                else:
                    return json.dumps({"error": f"HTTP {resp.status}"})
        except Exception as e:
            if attempt == retries - 1:
                return json.dumps({"error": str(e)})
            await asyncio.sleep(1)
    return json.dumps({"error": "Max retries exceeded"})

async def worker(input_queue, output_queue, pagerank):
    async with aiohttp.ClientSession() as session:
        while True:
            item = await input_queue.get()
            if item is None:
                break
            
            try:
                # 注入PageRank
                url = item.get("url", "")
                item["pagerank_score"] = pagerank.get(url, 0.0)
                
                # 获取LLM标签
                content = item.get("content", "")
                if content:
                    label = await fetch_label(session, content)
                    item["qwen_label"] = label
                else:
                    item["qwen_label"] = json.dumps({"error": "Empty content"})
                
                await output_queue.put(item)
            except Exception as e:
                item["qwen_label"] = json.dumps({"error": f"Worker error: {str(e)}"})
                await output_queue.put(item)
            finally:
                input_queue.task_done()

async def writer(output_queue, total, pbar):
    with open(OUTPUT_PATH, "a", encoding="utf-8") as fout:
        while True:
            item = await output_queue.get()
            if item is None:
                break
            fout.write(json.dumps(item, ensure_ascii=False) + "\n")
            fout.flush() # 确保实时写入
            output_queue.task_done()
            pbar.update(1)

async def main():
    # 1. 加载 PageRank
    print("Loading PageRank...")
    if os.path.exists(PAGERANK_PATH):
        with open(PAGERANK_PATH, "r", encoding="utf-8") as f:
            pagerank = json.load(f)
    else:
        print("Warning: PageRank file not found, using default score 0.0")
        pagerank = {}

    # 2. 检查断点
    processed_count = 0
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            for _ in f:
                processed_count += 1
    print(f"Resuming from line {processed_count}...")

    # 3. 计算总行数 (可选，为了进度条)
    total_lines = 0
    # 快速估算或读取
    # total_lines = sum(1 for _ in open(DATA_PATH)) # 太慢，略过或手动设置
    # 已知约 386082
    total_lines = 386082 

    # 4. 初始化队列
    input_queue = asyncio.Queue(maxsize=1000)
    output_queue = asyncio.Queue(maxsize=1000)

    # 5. 启动消费者
    workers = []
    for _ in range(CONCURRENCY):
        w = asyncio.create_task(worker(input_queue, output_queue, pagerank))
        workers.append(w)

    # 6. 启动写入者
    pbar = tqdm(total=total_lines, initial=processed_count, unit="doc")
    writer_task = asyncio.create_task(writer(output_queue, total_lines, pbar))

    # 7. 生产者：读取文件并推送到队列
    with open(DATA_PATH, "r", encoding="utf-8") as fin:
        # 跳过已处理
        for _ in range(processed_count):
            next(fin, None)
        
        for line in fin:
            try:
                item = json.loads(line)
                await input_queue.put(item)
            except:
                continue
    
    # 8. 发送结束信号
    for _ in range(CONCURRENCY):
        await input_queue.put(None)
    
    # 等待所有处理完成
    await input_queue.join()
    
    # 发送写入结束信号
    await output_queue.put(None)
    await writer_task
    
    pbar.close()
    print("Batch processing completed.")

if __name__ == "__main__":
    asyncio.run(main())
