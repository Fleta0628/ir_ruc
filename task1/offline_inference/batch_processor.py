# vLLM 原生离线推理脚本 (高性能版)
# 用于Task 1: 类别发现与离线数据增强
# 请确保运行前停止其他占用显存的进程 (如 vllm serve)

import os
import json
import sys
import re
import tiktoken
from vllm import LLM, SamplingParams
from tqdm import tqdm

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "../../crawled_data_deduplicated.jsonl")
PAGERANK_PATH = os.path.join(BASE_DIR, "../../pagerank_results.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "../../processed_data/enriched_data.jsonl")
MODEL_PATH = "/home/jiamin/Qwen/Qwen2.5-7B-Instruct"

# 批处理配置
# vLLM会自动处理内部batching，这里的BATCH_SIZE是一次性喂给vLLM引擎的请求数
# 建议设为 5000-10000，取决于内存
BATCH_SIZE = 5000 

# 导入提示模板
sys.path.append(BASE_DIR)
from prompt_templates import CATEGORY_PROMPT

CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT.replace("{", "{{").replace("}", "}}")
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT_SAFE.replace("{{content}}", "{content}")

def clean_markdown_json(text):
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
    if match:
        return match.group(1)
    return text

def smart_truncate(content, head_tokens=1000, tail_tokens=500):
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        tokens = enc.encode(content)
    except:
        return content[:5000]
    
    if len(tokens) <= head_tokens + tail_tokens:
        return content
    
    keep_tokens = tokens[:head_tokens] + tokens[-tail_tokens:]
    return enc.decode(keep_tokens, errors="ignore")

def main():
    # 1. 加载 PageRank
    print("Loading PageRank...")
    pagerank = {}
    if os.path.exists(PAGERANK_PATH):
        with open(PAGERANK_PATH, "r", encoding="utf-8") as f:
            pagerank = json.load(f)

    # 2. 检查断点
    processed_count = 0
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            for _ in f:
                processed_count += 1
    print(f"Resuming from line {processed_count}...")

    # 3. 初始化 vLLM
    print("Initializing vLLM Engine (TP=2)...")
    # 尝试修复 NCCL/显存问题
    os.environ["NCCL_P2P_DISABLE"] = "1" 
    llm = LLM(
        model=MODEL_PATH,
        tensor_parallel_size=2, # 使用双卡
        trust_remote_code=True,
        gpu_memory_utilization=0.85, # 降低显存占用
        max_model_len=4096,
        enforce_eager=True # 禁用CUDA Graph以提高稳定性
    )
    
    sampling_params = SamplingParams(
        temperature=0.2, 
        max_tokens=512
    )

    # 4. 数据处理循环
    total_lines = 386082 # 预估值
    pbar = tqdm(total=total_lines, initial=processed_count, unit="doc")
    
    with open(DATA_PATH, "r", encoding="utf-8") as f_in, open(OUTPUT_PATH, "a", encoding="utf-8") as f_out:
        # 跳过已处理
        for _ in range(processed_count):
            next(f_in, None)
        
        chunk_prompts = []
        chunk_items = []
        
        for line in f_in:
            try:
                item = json.loads(line)
            except:
                continue
                
            # 准备Prompt
            content = item.get("content", "")
            truncated = smart_truncate(content)
            prompt = CATEGORY_PROMPT_SAFE.format(content=truncated)
            # 添加对话格式 (Chat Template)
            # vLLM 的 generate 通常接受 string prompt，但也支持 chat list
            # 为了简单，我们手动构造 ChatML 格式或直接使用 tokenizer.apply_chat_template
            # 由于 LLM 类直接 generate，我们需要手动拼接 System/User
            # Qwen 2.5 模板: <|im_start|>system\n...<|im_end|>\n<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n
            
            # 使用 vLLM 的 tokenizer 转换
            messages = [
                {"role": "system", "content": "你是一个场景分类与数据增强专家。"},
                {"role": "user", "content": prompt}
            ]
            # 这里利用 LLM 内部 tokenizer
            # 但 llm.generate 接受 prompt_token_ids 或 prompt string
            # 我们先暂存 messages，批量转换会更快吗？
            # 简单起见，我们在收集时不做 apply_chat_template，在 generate 前做
            
            chunk_items.append(item)
            chunk_prompts.append(messages) # 暂存 messages 列表
            
            if len(chunk_prompts) >= BATCH_SIZE:
                # 批量推理
                # 注意：llm.generate 并不直接支持 messages 列表作为输入 (在旧版本)。
                # 新版 vLLM 支持 chat! 
                # 如果不支持，我们需要 tokenizer.apply_chat_template
                
                # 获取 tokenizer
                tokenizer = llm.get_tokenizer()
                prompts_formatted = [
                    tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                    for msgs in chunk_prompts
                ]
                
                outputs = llm.generate(prompts_formatted, sampling_params)
                
                # 写入结果
                for item, output in zip(chunk_items, outputs):
                    generated_text = output.outputs[0].text
                    
                    # 注入数据
                    item["qwen_label"] = clean_markdown_json(generated_text)
                    item["pagerank_score"] = pagerank.get(item.get("url", ""), 0.0)
                    
                    f_out.write(json.dumps(item, ensure_ascii=False) + "\n")
                
                f_out.flush()
                pbar.update(len(chunk_prompts))
                
                chunk_prompts = []
                chunk_items = []
        
        # 处理剩余
        if chunk_prompts:
            tokenizer = llm.get_tokenizer()
            prompts_formatted = [
                tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                for msgs in chunk_prompts
            ]
            outputs = llm.generate(prompts_formatted, sampling_params)
            for item, output in zip(chunk_items, outputs):
                generated_text = output.outputs[0].text
                item["qwen_label"] = clean_markdown_json(generated_text)
                item["pagerank_score"] = pagerank.get(item.get("url", ""), 0.0)
                f_out.write(json.dumps(item, ensure_ascii=False) + "\n")
            f_out.flush()
            pbar.update(len(chunk_prompts))

    pbar.close()
    print("Native batch processing completed.")

if __name__ == "__main__":
    main()
