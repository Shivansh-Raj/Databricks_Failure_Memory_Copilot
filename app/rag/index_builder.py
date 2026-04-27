import json
from embedder import embed_text
from vector_store import add_documents
from pathlib import Path 

incident_file_path = Path(__file__).parent.parent.parent / "data" / "incidents.json"

def build_semantic_document(incident):

    return f"""
        Error: {incident.get("error_message")}
        Tags: {incident.get("tags")}
        Severity: {incident.get("severity")}
        Root cause: {incident.get("root_cause", "")}
        Resolution: {incident.get("resolution")}
    """
    
def build_index():
    
    with open(incident_file_path, "r") as f:
        incidents = json.load(f)
        
    ids = []
    documents = []
    embeddings = []
    metadatas = []
    
    for incident in incidents:
        incident_id = incident.get("id")
        ids.append(incident_id)
        
        semantic_doc = build_semantic_document(incident)
        
        embedding = embed_text(semantic_doc)
        embeddings.append(embedding)
        documents.append(semantic_doc)
        metadatas.append(
            {
                "severity": incident.get("severity"),
                "tags": ",".join(incident.get("tags", []))
            }
        )
        
    add_documents(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    
if __name__ == "__main__":
    build_index()   