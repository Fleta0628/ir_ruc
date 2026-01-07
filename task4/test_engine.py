import sys
import os
import json

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from task4.answer_engine import AnswerEngine

def main():
    engine = AnswerEngine()
    
    test_queries = [
        "转专业资格",
        "人大科研基金申请流程",
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"{'='*50}")
        
        result = engine.generate_answer(query)
        
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nReferences:")
        for ref in result["references"]:
            print(f"[{ref['id']}] {ref['title']} ({ref['url']})")
        
        print(f"\nStats: Retrieval {result['retrieval_time']:.3f}s | Total {result['total_time']:.3f}s")

if __name__ == "__main__":
    main()
