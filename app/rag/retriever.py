from .embedder import embed_text
from .vector_store import query_documents

def retrieve_candidates(error_text: str, code_text:str = None, n_results = 3):
    """
    Retrieve similar historical incidents based on error text and optionally code context.
    """
    try:
        query_embedding = embed_text(f"Error: {error_text}\nCode Context: {code_text}")
        results = query_documents(query_embedding=query_embedding, n_results=n_results)
        candidates = []
        
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            candidates.append(
                {
                    "incident_id": results["ids"][0][i],
                    "document":    results["documents"][0][i],
                    "metadata":    results["metadatas"][0][i],
                    "score":       round(1 - distance, 4)  # convert distance → similarity score
                }
            )

        return candidates
    
    except:
        return []