from langchain_community.embeddings import HuggingFaceBgeEmbeddings
import config
import numpy as np

def test():
    model = HuggingFaceBgeEmbeddings(
        model_name=config.EMBEDDING_MODEL_PATH,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    emb = model.embed_query("test query")
    print(f"Embedding[:5]: {emb[:5]}")

if __name__ == "__main__":
    test()
