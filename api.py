import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
ROOT = Path(__file__).parent
INDEX_DIR = ROOT / "data" / "faiss_index"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
K = int(os.getenv("RETRIEVER_K", "4"))

app = FastAPI(title="Tamil Nadu Agriculture Schemes RAG API", version="1.0.0")
vectorstore = None
llm = None
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a careful Tamil Nadu agriculture scheme information assistant.
Answer using ONLY the supplied retrieved context. Do not use outside knowledge or claim you checked the web.
If the context does not contain the answer, clearly say the indexed documents do not provide enough information and direct the user to the official source listed in the context.
Do not invent eligibility, subsidy amounts, deadlines, application links, or required documents.
Respond in the language of the question (Tamil or English). Explain acronyms simply.
Distinguish current confirmed details from older policy notes. Mention the source URL(s) used.
Use concise headings: Scheme, Who can apply, Benefits, Documents / How to apply, Source. Only include sections supported by context.
Context:
{context}"""),
    ("human", "{question}")
])

@app.on_event("startup")
def load_index():
    global vectorstore, llm
    if not INDEX_DIR.exists():
        print("FAISS index missing. Run ingest.py and build_index.py before starting the API.")
        return
    embeddings = OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    # This index is created by this project; allow dangerous deserialization for its local FAISS metadata.
    vectorstore = FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
    llm = ChatOpenAI(model=MODEL, temperature=0)

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)

class Source(BaseModel):
    title: str
    url: str
    excerpt: str

class AskResponse(BaseModel):
    answer: str
    sources: List[Source]

@app.get("/")
def root():
    return {"message": "Tamil Nadu Agriculture Schemes RAG API", "index_loaded": vectorstore is not None, "model": MODEL}

@app.get("/health")
def health():
    return {"status": "ok" if vectorstore is not None else "index_missing", "index_loaded": vectorstore is not None}

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if vectorstore is None or llm is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded. Run ingest.py and build_index.py first.")
    try:
        docs = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": K}).invoke(request.question)
        if not docs:
            return AskResponse(answer="I couldn't find relevant information in the indexed official documents. Please check the relevant Tamil Nadu government department.", sources=[])
        context_parts = []
        sources = []
        seen = set()
        for doc in docs:
            url = doc.metadata.get("source", "Source URL unavailable")
            title = doc.metadata.get("title", "Official scheme information")
            context_parts.append(f"Source URL: {url}\nTitle: {title}\nContent:\n{doc.page_content}")
            if url not in seen:
                seen.add(url)
                sources.append(Source(title=title, url=url, excerpt=doc.page_content[:400].replace("\n", " ")))
        chain = prompt | llm
        response = chain.invoke({"context": "\n\n---\n\n".join(context_parts), "question": request.question})
        return AskResponse(answer=response.content if isinstance(response.content, str) else str(response.content), sources=sources)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG request failed: {exc}")
