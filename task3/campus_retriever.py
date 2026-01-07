import os
import sys
import json
import pickle
import time
import jieba
import numpy as np
from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from openai import OpenAI

# Add parent directory to sys.path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

class CampusRetriever:
    def __init__(self):
        print("Initializing CampusRetriever (vLLM Client Mode)...")
        self.device_embedding = config.DEVICE_EMBEDDING
        
        # 1. Load BM25 Index
        print(f"Loading BM25 index from {config.BM25_INDEX_PATH}...")
        with open(config.BM25_INDEX_PATH, "rb") as f:
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.bm25_metadata = data["metadata"]
            print(f"   -> Loaded {len(self.bm25_metadata)} documents for BM25.")
            
        # 2. Load Vector Store
        print(f"Loading Vector Store from {config.CHROMA_DB_DIR}...")
        self.embedding_model = HuggingFaceBgeEmbeddings(
            model_name=config.EMBEDDING_MODEL_PATH,
            model_kwargs={'device': self.device_embedding},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vector_store = Chroma(
            persist_directory=config.CHROMA_DB_DIR,
            embedding_function=self.embedding_model,
            collection_name="ruc_campus_knowledge_base"
        )
        print("   -> Vector Store loaded.")
        
        # 3. Initialize OpenAI Client for vLLM
        print(f"Initializing vLLM Client at {config.LLM_API_URL}...")
        self.client = OpenAI(
            base_url=config.LLM_API_URL,
            api_key=config.LLM_API_KEY
        )
        self.model_name = config.LLM_MODEL_NAME
        print(f"   -> Client ready (Target Model: {self.model_name})")

        # Pre-initialize jieba
        jieba.initialize()

    def _detect_intent(self, query: str) -> Dict[str, float]:
        """
        Use vLLM API to detect intent probabilities.
        """
        system_prompt = (
            "You are a query intent classifier for a university search engine. "
            "Analyze the user's query and assign probabilities (0.0 to 1.0) to these categories: "
            "News (news, events, notifications), "
            "Research (papers, labs, professors, academic), "
            "Education (courses, admissions, campus life, admin). "
            "Output strictly valid JSON only. Example: {\"News\": 0.1, \"Research\": 0.8, \"Education\": 0.1}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=128,
                temperature=0.1
            )
            content = response.choices[0].message.content
            
            # Parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                return json.loads(json_str)
            else:
                print(f"   [Router Warning] JSON not found in response: {content}")
        except Exception as e:
            print(f"   [Router Error] API Call failed: {e}")
            print("   -> Is vLLM running? Start it with `scripts/start_vllm.sh`")
            
        return {"News": 0.33, "Research": 0.33, "Education": 0.33}

    def _search_vector(self, query: str, top_k: int = 50) -> List[Dict]:
        results = self.vector_store.similarity_search_with_score(query, k=top_k)
        
        processed_results = []
        for doc, score in results:
            # Convert L2 distance to similarity
            sim_score = 1.0 / (1.0 + score) 
            
            processed_results.append({
                "doc": doc,
                "score_vec": sim_score,
                "type": "vector"
            })
        return processed_results

    def _search_bm25(self, query: str, top_k: int = 50) -> List[Dict]:
        tokenized_query = list(jieba.cut_for_search(query))
        scores = self.bm25.get_scores(tokenized_query)
        
        top_n_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_n_indices:
            score = scores[idx]
            if score <= 0: continue
            
            metadata = self.bm25_metadata[idx]
            results.append({
                "metadata": metadata,
                "score_bm25": score,
                "type": "bm25"
            })
        return results

    def _normalize_scores(self, results: List[Dict], key: str):
        if not results: return
        scores = [r[key] for r in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            for r in results: r[f"norm_{key}"] = 1.0
        else:
            for r in results:
                r[f"norm_{key}"] = (r[key] - min_s) / (max_s - min_s)

    def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        start_time = time.time()
        
        # 1. Intent Detection
        print(f"--- Processing Query: {query} ---")
        intent = self._detect_intent(query)
        print(f"   -> Detected Intent: {intent}")
        
        # 2. Parallel Retrieval
        vec_results = self._search_vector(query, top_k=config.TOP_K_VECTOR)
        bm25_results = self._search_bm25(query, top_k=config.TOP_K_BM25)
        
        # 3. Merge & Rerank
        merged_docs = {}
        
        # Process Vector Results
        self._normalize_scores(vec_results, "score_vec")
        for res in vec_results:
            url = res["doc"].metadata.get("url")
            if not url: continue
            
            if url not in merged_docs:
                merged_docs[url] = {
                    "url": url,
                    "title": res["doc"].metadata.get("title", ""),
                    "pagerank": float(res["doc"].metadata.get("pagerank", 0.0)),
                    "categories": res["doc"].metadata.get("categories", ""),
                    "content_preview": res["doc"].page_content[:200],
                    "full_content": res["doc"].page_content,
                    "vec_score": res["score_vec"],
                    "norm_vec_score": res.get("norm_score_vec", 0.0),
                    "bm25_score": 0.0,
                    "norm_bm25_score": 0.0,
                    "sources": ["vector"]
                }
            else:
                if res["score_vec"] > merged_docs[url]["vec_score"]:
                    merged_docs[url]["vec_score"] = res["score_vec"]
                    merged_docs[url]["norm_vec_score"] = res.get("norm_score_vec", 0.0)
                    merged_docs[url]["content_preview"] = res["doc"].page_content[:200]
                    merged_docs[url]["full_content"] = res["doc"].page_content

        # Process BM25 Results
        self._normalize_scores(bm25_results, "score_bm25")
        for res in bm25_results:
            url = res["metadata"].get("url")
            if not url: continue
            
            if url not in merged_docs:
                merged_docs[url] = {
                    "url": url,
                    "title": res["metadata"].get("title", ""),
                    "pagerank": float(res["metadata"].get("pagerank", 0.0)),
                    "categories": "", 
                    "content_preview": "(From BM25 Index)",
                    "full_content": None,
                    "vec_score": 0.0,
                    "norm_vec_score": 0.0,
                    "bm25_score": res["score_bm25"],
                    "norm_bm25_score": res.get("norm_score_bm25", 0.0),
                    "sources": ["bm25"]
                }
            else:
                merged_docs[url]["bm25_score"] = res["score_bm25"]
                merged_docs[url]["norm_bm25_score"] = res.get("norm_score_bm25", 0.0)
                if "bm25" not in merged_docs[url]["sources"]:
                    merged_docs[url]["sources"].append("bm25")

        # 4. Final Scoring
        candidates = list(merged_docs.values())
        if not candidates:
            return {"intent": intent, "results": [], "time": time.time() - start_time}

        pr_scores = [c["pagerank"] for c in candidates]
        pr_log_scores = [np.log1p(pr * 1000) for pr in pr_scores] 
        min_pr, max_pr = min(pr_log_scores), max(pr_log_scores)
        
        for i, c in enumerate(candidates):
            if max_pr > min_pr:
                c["norm_pr"] = (pr_log_scores[i] - min_pr) / (max_pr - min_pr)
            else:
                c["norm_pr"] = 0.0
                
            doc_cats = c["categories"].split(",") if c["categories"] else []
            intent_score = 0.0
            for cat, prob in intent.items():
                for doc_cat in doc_cats:
                    if cat.lower() in doc_cat.lower():
                        intent_score += prob
            
            c["intent_boost"] = min(intent_score, 1.0)
            
            # Weighted Scoring (Favoring BM25)
            c["final_score"] = (
                0.1 * c["norm_vec_score"] +
                0.7 * c["norm_bm25_score"] +
                0.1 * c["norm_pr"] +
                0.1 * c["intent_boost"]
            )
            
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Deduplication (SimCheck): Filter out documents with identical titles
        unique_candidates = []
        seen_titles = set()
        
        for cand in candidates:
            title = cand.get("title", "").strip()
            if title and title in seen_titles:
                continue
            
            if title:
                seen_titles.add(title)
            
            unique_candidates.append(cand)
            if len(unique_candidates) >= top_k:
                break
        
        return {
            "intent": intent,
            "results": unique_candidates,
            "time": time.time() - start_time
        }

if __name__ == "__main__":
    retriever = CampusRetriever()
    res = retriever.search("人大科研基金申请")
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
