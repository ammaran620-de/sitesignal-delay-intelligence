from app.construction_rag import ingest_construction_evidence

if __name__ == "__main__":
    count = ingest_construction_evidence()
    print(f"Indexed {count} construction evidence chunks in the SiteSignal ChromaDB collection.")
