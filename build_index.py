"""Build the persistent FAISS index from the saved corpus; no web requests are made here."""
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
ROOT = Path(__file__).parent
DATA = ROOT / "data"
CORPUS = DATA / "master_corpus.txt"
INDEX_DIR = DATA / "faiss_index"
SOURCES = DATA / "sources.jsonl"

def main():
    if not CORPUS.exists():
        raise SystemExit("Missing data/master_corpus.txt. Run python ingest.py first.")
    if INDEX_DIR.exists():
        print("FAISS index already exists; skipping rebuild. Delete data/faiss_index to rebuild intentionally.")
        return
    raw = CORPUS.read_text(encoding="utf-8")
    # Keep each source block together as a document where possible.
    source_records = []
    if SOURCES.exists():
        source_records = [json.loads(line) for line in SOURCES.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Corpus source markers allow source attribution even if source metadata is imperfect.
    blocks = [b.strip() for b in raw.split("=" * 90) if b.strip()]
    docs = []
    for block in blocks:
        first_lines = block.splitlines()[:4]
        source = next((line.replace("SOURCE: ", "").strip() for line in first_lines if line.startswith("SOURCE: ")), "Official source (see corpus)")
        title = next((line.replace("TITLE: ", "").strip() for line in first_lines if line.startswith("TITLE: ")), "Agriculture scheme information")
        docs.append(Document(page_content=block, metadata={"source": source, "title": title}))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "။", ". ", " ", ""],
        add_start_index=True,
    )
    chunks = splitter.split_documents(docs)
    if not chunks:
        raise SystemExit("No text chunks found. Check the corpus extraction.")
    embeddings = OpenAIEmbeddings(model=__import__("os").getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(str(INDEX_DIR))
    print(f"Indexed {len(docs)} source documents into {len(chunks)} chunks.")
    print(f"Persistent index saved at: {INDEX_DIR}")

if __name__ == "__main__":
    main()
