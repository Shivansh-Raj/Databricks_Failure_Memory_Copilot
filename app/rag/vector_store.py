import chromadb
from chromadb.config import Settings
from pathlib import Path

vector_db_path = (Path(__file__).parent.parent.parent / "data" / "vector_index").resolve()
vector_db_path.mkdir(parents=True, exist_ok=True)

client = None
collection = None

def get_collection():
    global client, collection
    if collection is None:
        # client = chromadb.PersistentClient(
        #     Settings(
        #         persistent_directory = str(vector_db_path),
        #         anonymized_telemetry=False        
        #     )
        # )
        client = chromadb.PersistentClient(
            path = str(vector_db_path)
        )
        
        collection = client.get_or_create_collection(
            name = "incidents_collection"
        )

    return collection

def add_documents(ids, embeddings, metadatas, documents):
    collection = get_collection()
    
    result = collection.add(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents
    )
    
    return result

def query_documents(query_embedding, n_results = 3):
    collection = get_collection()
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )

    return results

