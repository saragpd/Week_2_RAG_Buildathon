# Tamil Nadu Agriculture Schemes RAG Chatbot

A starter project using LangChain, OpenAI, LangSmith, FAISS, FastAPI, Playwright, and Streamlit.

## Architecture
- `ingest.py`: one-time ingestion of configured official websites and linked PDFs; saves a combined corpus and source metadata.
- `build_index.py`: chunks the saved corpus, creates OpenAI embeddings, and persists FAISS locally.
- `api.py`: FastAPI backend; loads the saved FAISS index and answers from retrieved context only.
- `app.py`: Streamlit agriculture-themed chat UI.

## Setup (Windows PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```
Edit `.env` and set `OPENAI_API_KEY`. Optional: set `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

## Run ingestion once
```powershell
python ingest.py
python build_index.py
```
The crawler uses the configured official starting URLs and collects linked PDF files and page text. Review `data/master_corpus.txt` and `data/sources.jsonl` before indexing. Some sites may block automated requests or change their layout; add specific official URLs manually to `SOURCE_URLS` in `ingest.py` if needed.

**No web search occurs when a farmer asks a question.** The API only loads the local FAISS index. To refresh the index intentionally, remove `data/faiss_index/` and rerun `python build_index.py`. To rebuild the corpus, run `python ingest.py --rebuild` and then rebuild the index.

## Start the app (two terminals)
Terminal 1:
```powershell
uvicorn api:app --reload --port 8000
```
Terminal 2:
```powershell
streamlit run app.py
```

## Chunking and retrieval
- `chunk_size=1000` characters
- `chunk_overlap=200` characters (20% overlap)
- `k=4` retrieved chunks as a starting point; evaluate k=3, 4, 5, 6 against a small test set before finalizing.
These are practical initial settings, not universal optimums. For long policy PDFs, consider token-aware splitting and evaluate retrieval quality.

## Data quality and safety
- Official scheme details change. Record publication/update dates and verify active status before production use.
- The crawler is a convenience, not a guarantee that it captures every page/PDF. Check the source manifest.
- The assistant is instructed to say when the corpus does not contain the answer rather than invent benefits, deadlines, or eligibility.
- Do not commit `.env`, API keys, or other secrets.
