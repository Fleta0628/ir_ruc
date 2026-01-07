import sys
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

PERSIST_DIRECTORY = "task2/chroma_db"
MODEL_PATH = "/home/jiamin/RuC_courses/assignment1/work3/models/bge-m3"

def check_db():
    print("Loading Embedding Model...")
    # Use CPU for quick check
    embeddings = HuggingFaceBgeEmbeddings(
        model_name=MODEL_PATH,
        model_kwargs={'device': 'cpu'}, 
        encode_kwargs={'normalize_embeddings': True}
    )
    
    print("Loading Vector Store...")
    vectorstore = Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings,
        collection_name="ruc_campus_knowledge_base"
    )
    
    print("Fetching sample...")
    # Get 1 document
    results = vectorstore.get(limit=1)
    
    if results['ids']:
        print("\n=== Sample Document ===")
        print(f"ID: {results['ids'][0]}")
        print(f"Metadata: {results['metadatas'][0]}")
        print(f"Document Content (First 500 chars): \n{results['documents'][0][:500]}...")
    else:
        print("Database is empty!")

if __name__ == "__main__":
    check_db()
