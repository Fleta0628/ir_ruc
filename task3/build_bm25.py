import os
import json
import pickle
import jieba
from tqdm import tqdm
from rank_bm25 import BM25Okapi
import config

def build_bm25():
    print("Step 1: Reading data...")
    if not os.path.exists(config.ENRICHED_DATA_PATH):
        print(f"Error: File not found {config.ENRICHED_DATA_PATH}")
        return

    corpus = []
    doc_metadata = [] # 存储对应索引的元数据 (url, title, pagerank)
    
    # 预加载 jieba
    jieba.initialize()

    with open(config.ENRICHED_DATA_PATH, 'r', encoding='utf-8') as f:
        # 使用 tqdm 显示进度
        # 为了避免内存溢出，如果数据量极大，可能需要流式处理。
        # 但 40w 条短文本 (title+summary+queries) 应该可以放入 24G 内存机器的 RAM 中 (通常有 64G+ RAM)
        for line in tqdm(f, desc="Tokenizing"):
            try:
                item = json.loads(line)
                
                # 解析 qwen_label
                qwen_label = item.get("qwen_label", {})
                if isinstance(qwen_label, str):
                    try:
                        qwen_label = json.loads(qwen_label)
                    except:
                        qwen_label = {}
                
                title = item.get("title", "")
                url = item.get("url", "")
                pagerank = item.get("pagerank_score", 0.0)
                
                summary = qwen_label.get("summary", "")
                queries = qwen_label.get("potential_queries", [])
                if isinstance(queries, list):
                    queries_str = " ".join(queries)
                else:
                    queries_str = str(queries)

                # 组合文本：Title + Summary + Queries
                # 这种组合包含了最高密度的语义信息
                text_to_index = f"{title} {summary} {queries_str}"
                
                # 分词 - 使用搜索引擎模式
                tokens = list(jieba.cut_for_search(text_to_index))
                corpus.append(tokens)
                
                doc_metadata.append({
                    "url": url,
                    "title": title,
                    "pagerank": pagerank
                })
                
            except Exception as e:
                continue

    print(f"Step 2: Building BM25 index for {len(corpus)} documents...")
    bm25 = BM25Okapi(corpus)
    
    print(f"Step 3: Saving index to {config.BM25_INDEX_PATH}...")
    with open(config.BM25_INDEX_PATH, "wb") as f:
        pickle.dump({
            "bm25": bm25,
            "metadata": doc_metadata
        }, f)
        
    print("Done!")

if __name__ == "__main__":
    build_bm25()
