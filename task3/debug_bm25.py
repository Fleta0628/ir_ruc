import pickle
import jieba
import config
import numpy as np

def debug_bm25():
    print(f"Loading BM25 index from {config.BM25_INDEX_PATH}...")
    with open(config.BM25_INDEX_PATH, "rb") as f:
        data = pickle.load(f)
        bm25 = data["bm25"]
        metadata = data["metadata"]

    query = "人大科研基金申请流程"
    tokens = list(jieba.cut_for_search(query))
    print(f"Query Tokens: {tokens}")
    
    scores = bm25.get_scores(tokens)
    top_n = np.argsort(scores)[::-1][:10]
    
    print("\nTop 10 BM25 Results:")
    for idx in top_n:
        score = scores[idx]
        meta = metadata[idx]
        print(f"Score: {score:.4f} | Title: {meta['title']} | URL: {meta['url']}")
        
    # Check specifically for the document we found via grep
    target_url_partial = "a2c6d8cc33e44c4880fda9638c86a3ea.htm"
    found = False
    for i, meta in enumerate(metadata):
        if target_url_partial in meta["url"]:
            found = True
            doc_score = scores[i]
            print(f"\nTarget Document Found at index {i}:")
            print(f"Title: {meta['title']}")
            print(f"URL: {meta['url']}")
            print(f"Score for query: {doc_score}")
            # Analyze why score is low/high
            # We can't easily see the doc content in BM25 object directly without corpus
            break
            
    if not found:
        print(f"\nTarget document {target_url_partial} NOT found in metadata!")

if __name__ == "__main__":
    debug_bm25()
