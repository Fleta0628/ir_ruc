import sys
import os
import time

# 1. 强制开启行缓冲，确保 print 能够立即输出，不会被缓存
sys.stdout.reconfigure(line_buffering=True)

print("Step 1: Script started. Initializing lightweight modules...", flush=True)

def process_data():
    print("Step 2: Starting Heavy Imports (Torch, Langchain)... This may take 10-30 seconds.", flush=True)
    
    try:
        import json
        import gc
        # 记录 import 开始时间
        start_import = time.time()
        
        import torch
        print(f"   -> Torch imported ({time.time() - start_import:.2f}s).", flush=True)
        
        from tqdm import tqdm
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document
        
        print(f"   -> All libraries imported ({time.time() - start_import:.2f}s total).", flush=True)
        
    except Exception as e:
        print(f"!!! CRITICAL ERROR during imports: {e}", flush=True)
        return

    # Configuration
    INPUT_FILE = "processed_data/enriched_data.jsonl"
    PERSIST_DIRECTORY = "task2/chroma_db"
    BATCH_SIZE = 100
    CHUNK_SIZE = 8000 
    CHUNK_OVERLAP = 500
    
    # Check for GPU
    print("Step 3: Checking GPU status...", flush=True)
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"   -> Using device: {device}", flush=True)
        
        if device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            mem_alloc = torch.cuda.memory_allocated(0) / 1024**3
            mem_reserved = torch.cuda.memory_reserved(0) / 1024**3
            print(f"   -> GPU Name: {gpu_name}", flush=True)
            print(f"   -> Memory State: Allocated={mem_alloc:.2f}GB, Reserved={mem_reserved:.2f}GB", flush=True)
            
            # 测试简单的 tensor 操作，确保 CUDA 没死锁
            x = torch.tensor([1.0]).to(device)
            print("   -> Simple CUDA tensor test passed.", flush=True)
            
    except Exception as e:
        print(f"!!! Error checking device: {e}", flush=True)
        device = "cpu"

    print("Step 4: Loading Local Embedding Model...", flush=True)
    model_name = "/home/jiamin/RuC_courses/assignment1/work3/models/bge-m3"
    
    # 显式检查路径
    if not os.path.exists(model_name):
        print(f"!!! ERROR: Local model path does not exist: {model_name}", flush=True)
        print("    Please check the path spelling carefully.", flush=True)
        return

    model_kwargs = {'device': device}
    encode_kwargs = {'normalize_embeddings': True, 'batch_size': 16}
    
    try:
        embeddings = HuggingFaceBgeEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        print("   -> Embedding Model loaded successfully.", flush=True)
    except Exception as e:
        print(f"!!! Error loading embedding model: {e}", flush=True)
        sys.exit(1)

    print("Step 5: Initializing ChromaDB Vector Store...", flush=True)
    try:
        # 检查目录权限
        if not os.path.exists(os.path.dirname(PERSIST_DIRECTORY)):
             os.makedirs(os.path.dirname(PERSIST_DIRECTORY), exist_ok=True)
             
        vectorstore = Chroma(
            persist_directory=PERSIST_DIRECTORY,
            embedding_function=embeddings,
            collection_name="ruc_campus_knowledge_base"
        )
        print("   -> ChromaDB initialized.", flush=True)
    except Exception as e:
        print(f"!!! Error initializing ChromaDB: {e}", flush=True)
        sys.exit(1)

    print("Step 6: Initializing Text Splitter...", flush=True)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    print(f"Step 7: Preparing to read {INPUT_FILE}...", flush=True)
    documents = []
    
    if not os.path.exists(INPUT_FILE):
        print(f"!!! Input file {INPUT_FILE} not found!", flush=True)
        sys.exit(1)
            
    # 不计算总行数，直接开始循环，避免长时间等待
    print("   -> Starting data processing loop...", flush=True)
    
    count_processed = 0
    count_batches = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        # 使用 tqdm 但不指定 total，避免预读取
        for line in tqdm(f, desc="Processing Records (Streaming)"):
            try:
                record = json.loads(line)
                
                # --- 数据解析逻辑 ---
                qwen_label_str = record.get('qwen_label', '{}')
                try:
                    if isinstance(qwen_label_str, str):
                        qwen_label = json.loads(qwen_label_str)
                    else:
                        qwen_label = qwen_label_str
                except json.JSONDecodeError:
                    qwen_label = {}

                url = record.get('url', '')
                title = record.get('title', '')
                content = record.get('content', '')
                pagerank = record.get('pagerank_score', 0.0)
                
                soft_categories = qwen_label.get('soft_categories', [])
                if isinstance(soft_categories, list):
                    categories_str = ",".join(soft_categories)
                else:
                    categories_str = str(soft_categories)
                    
                potential_queries = qwen_label.get('potential_queries', [])
                if isinstance(potential_queries, list):
                    queries_str = " ".join([q for q in potential_queries if q])
                else:
                    queries_str = str(potential_queries)
                    
                summary = qwen_label.get('summary', '')
                # ---------------------

                if not content or not content.strip():
                    continue

                chunks = text_splitter.split_text(content)
                
                for chunk in chunks:
                    enhanced_text = f"Title: {title}\nSummary: {summary}\nQueries: {queries_str}\nContent: {chunk}"
                    
                    metadata = {
                        "url": url,
                        "categories": categories_str,
                        "pagerank": float(pagerank) if pagerank is not None else 0.0,
                        "title": title
                    }
                    
                    doc = Document(page_content=enhanced_text, metadata=metadata)
                    documents.append(doc)
                    
                    if len(documents) >= BATCH_SIZE:
                        # 核心写入操作
                        vectorstore.add_documents(documents)
                        documents = []
                        gc.collect()
                        
                        count_batches += 1
                        # 每写入 5 个 batch 显式打印一次，证明程序活着
                        if count_batches % 5 == 0:
                            print(f"   [Alive Check] Written {count_batches * BATCH_SIZE} docs to Chroma...", flush=True)
                        
            except json.JSONDecodeError:
                continue
            except Exception as e:
                # 打印第一个错误以便调试
                if count_processed == 0:
                     print(f"!!! Error in loop: {e}", flush=True)
                continue
            
            count_processed += 1

    # Add remaining documents
    if documents:
        print(f"   -> Adding final batch of {len(documents)} documents...", flush=True)
        vectorstore.add_documents(documents)

    print(f"Index creation complete. Saved to {PERSIST_DIRECTORY}", flush=True)

if __name__ == "__main__":
    process_data()