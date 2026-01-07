import sys
import os
import json
import time
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Any, Optional

# Add parent directory for config and task3
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import task3.config as config
from task3.campus_retriever import CampusRetriever

class AnswerEngine:
    def __init__(self):
        print("Initializing AnswerEngine...")
        # 1. Initialize Retriever
        self.retriever = CampusRetriever()
        
        # 2. Load Content Map (Enriched Data)
        print("Loading enriched data for full content lookup...")
        self.url_map = {}
        try:
            if os.path.exists(config.ENRICHED_DATA_PATH):
                with open(config.ENRICHED_DATA_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            item = json.loads(line)
                            url = item.get("url")
                            if url:
                                self.url_map[url] = item
                        except:
                            continue
                print(f"   -> Loaded {len(self.url_map)} documents into memory map.")
            else:
                print(f"   [Warning] Enriched data not found at {config.ENRICHED_DATA_PATH}")
        except Exception as e:
            print(f"   [Error] Failed to load enriched data: {e}")
            
        # 3. OpenAI Client (Using task3 config)
        print(f"Initializing Generator Client (Target: {config.LLM_MODEL_NAME})...")
        self.client = OpenAI(
            base_url=config.LLM_API_URL,
            api_key=config.LLM_API_KEY
        )
        self.model_name = config.LLM_MODEL_NAME

    def _get_document_content(self, doc_result: Dict) -> str:
        """
        Get content for a document result. 
        Prioritize 'full_content' (from Vector Search).
        Fallback to 'url_map' (for BM25).
        Enforce strict length limit to fit 4096 context window.
        """
        limit = 600  # 5 docs * 600 chars ~= 3000 chars < 3000 tokens (safe)
        
        content = ""
        
        # Case 1: Vector Search Result (has chunk)
        if doc_result.get("full_content"):
            content = doc_result["full_content"]
            
        # Case 2: BM25 Result (needs lookup)
        else:
            url = doc_result.get("url")
            if url and url in self.url_map:
                item = self.url_map[url]
                qwen_label = item.get("qwen_label", {})
                if isinstance(qwen_label, str):
                    try:
                        qwen_label = json.loads(qwen_label)
                    except:
                        qwen_label = {}
                
                summary = qwen_label.get("summary", "")
                raw_content = item.get("content", "")
                
                # If summary is missing, just use content
                if summary:
                    content = f"Summary: {summary}\nContent: {raw_content}"
                else:
                    content = f"Content: {raw_content}"
            else:
                return "Content not available."
        
        # Global Truncation
        if len(content) > limit:
            return content[:limit] + "..."
        return content

    def generate_answer(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        
        # 1. Retrieve
        print(f"--- Generating Answer for: {query} ---")
        retrieval_res = self.retriever.search(query, top_k=5)
        results = retrieval_res["results"]
        intent = retrieval_res["intent"]
        
        # 2. Build Context
        context_parts = []
        references = []
        
        for i, doc in enumerate(results):
            content = self._get_document_content(doc)
            ref_id = i + 1
            
            context_parts.append(f"[{ref_id}] Title: {doc['title']}\nURL: {doc['url']}\n{content}\n")
            
            references.append({
                "id": ref_id,
                "title": doc['title'],
                "url": doc['url'],
                "score": doc['final_score']
            })
            
        context_str = "\n".join(context_parts)
        
        # 3. Construct Prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        system_prompt = (
            f"Current Date: {current_date}\n"
            "You are RUC-Bot, an intelligent AI assistant for Renmin University of China.\n"
            "Answer the user's question based strictly on the provided context.\n"
            "Rules:\n"
            "1. Use clear, professional, yet helpful tone.\n"
            "2. Cite your sources using [1], [2] format corresponding to the provided context.\n"
            "3. If the context contains the answer, summarize it well.\n"
            "4. If the context does NOT contain the answer, explicitly state 'Based on the retrieved documents, I cannot answer this question.' Do not hallucinate.\n"
            "5. Handle time-sensitive queries (e.g. 'next week', 'deadline') using the Current Date."
        )
        
        user_prompt = (
            f"User Query: {query}\n\n"
            f"Detected Intent: {intent}\n\n"
            f"Retrieved Context:\n{context_str}\n\n"
            "Answer:"
        )
        
        # 4. Generate
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1024,
                temperature=0.3
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"Error generating answer: {e}"
            
        return {
            "query": query,
            "answer": answer,
            "references": references,
            "intent": intent,
            "retrieval_time": retrieval_res["time"],
            "total_time": time.time() - start_time
        }

    def generate_answer_stream(self, query: str) -> Any:
        """
        Stream version of generate_answer.
        Yields:
            Dict: Metadata (first yield only) containing intent, references, etc.
            Dict: Content chunks from LLM.
        """
        # 1. Retrieve
        print(f"--- Generating Answer Stream for: {query} ---")
        retrieval_res = self.retriever.search(query, top_k=5)
        results = retrieval_res["results"]
        intent = retrieval_res["intent"]
        
        # 2. Build Context & References
        context_parts = []
        references = []
        
        for i, doc in enumerate(results):
            content = self._get_document_content(doc)
            ref_id = i + 1
            context_parts.append(f"[{ref_id}] Title: {doc['title']}\nURL: {doc['url']}\n{content}\n")
            
            # Determine Authority Level based on normalized PageRank
            norm_pr = doc.get("norm_pr", 0.0)
            if norm_pr >= 0.7:
                authority = "High"
            elif norm_pr >= 0.3:
                authority = "Medium"
            else:
                authority = "Low"
                
            references.append({
                "id": ref_id,
                "title": doc['title'],
                "url": doc['url'],
                "authority": authority,
                "score": doc['final_score'],
                "details": {
                    "vector": doc.get("norm_vec_score", 0.0),
                    "bm25": doc.get("norm_bm25_score", 0.0),
                    "pr": norm_pr,
                    "raw_content": content[:300] + "..." 
                }
            })
            
        context_str = "\n".join(context_parts)
        
        # Yield Metadata first
        yield {
            "type": "meta",
            "intent": intent,
            "references": references,
            "retrieval_time": retrieval_res["time"]
        }
        
        # 3. Construct Prompt (Same as before)
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = (
            f"Current Date: {current_date}\n"
            "You are RUC-Bot, an intelligent AI assistant for Renmin University of China.\n"
            "Answer the user's question based strictly on the provided context.\n"
            "Rules:\n"
            "1. Use clear, professional, yet helpful tone.\n"
            "2. Cite your sources using [1], [2] format corresponding to the provided context.\n"
            "3. If the context contains the answer, summarize it well.\n"
            "4. If the context does NOT contain the answer, explicitly state 'Based on the retrieved documents, I cannot answer this question.' Do not hallucinate.\n"
            "5. Handle time-sensitive queries (e.g. 'next week', 'deadline') using the Current Date."
        )
        user_prompt = (
            f"User Query: {query}\n\n"
            f"Detected Intent: {intent}\n\n"
            f"Retrieved Context:\n{context_str}\n\n"
            "Answer:"
        )
        
        # 4. Generate Stream
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1024,
                temperature=0.3,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield {
                        "type": "content",
                        "content": content
                    }
        except Exception as e:
            yield {
                "type": "content",
                "content": f"Error generating answer: {e}"
            }
