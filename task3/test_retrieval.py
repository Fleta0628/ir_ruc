import json
import time
from task3.campus_retriever import CampusRetriever

def main():
    print("Step 1: Initializing System...")
    retriever = CampusRetriever()
    
    test_queries = [
        "人大科研基金申请流程",
        "下周有什么学术讲座",
        "教务处联系电话",
        "图书馆开馆时间",
        "2024年本科招生简章"
    ]
    
    print("\nStep 2: Running Tests...")
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"{'='*50}")
        
        result = retriever.search(query, top_k=3)
        
        print(f"Intent Distribution: {result['intent']}")
        print(f"Time Taken: {result['time']:.4f}s")
        print("\nTop 3 Results:")
        
        for i, doc in enumerate(result["results"]):
            print(f"\nRank {i+1}:")
            print(f"   Title: {doc['title']}")
            print(f"   URL: {doc['url']}")
            print(f"   Score: {doc['final_score']:.4f}")
            print(f"   Sources: {doc['sources']}")
            print(f"   Categories: {doc['categories']}")
            print(f"   Intent Boost: {doc['intent_boost']:.2f}")
            print(f"   Scores -> Vec: {doc['norm_vec_score']:.2f} | BM25: {doc['norm_bm25_score']:.2f} | PR: {doc['norm_pr']:.2f}")
            print(f"   Preview: {doc['content_preview'].replace('\n', ' ')[:100]}...")

if __name__ == "__main__":
    main()
