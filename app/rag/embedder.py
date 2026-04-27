from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-base-en-v1.5')

def embed_text(text):
    return model.encode(text).tolist()