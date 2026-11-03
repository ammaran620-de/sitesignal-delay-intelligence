from app.rag import ingest_policies

if __name__ == "__main__":
    count = ingest_policies()
    print(f"Ingested {count} policy chunks into the local ChromaDB collection.")
