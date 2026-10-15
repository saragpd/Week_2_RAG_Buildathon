"""One-time source ingestion. Review downloaded content and source manifest before indexing."""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

load_dotenv()
ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOWNLOADS = DATA / "downloads"
CORPUS = DATA / "master_corpus.txt"
SOURCES = DATA / "sources.jsonl"
MANIFEST = DATA / "ingestion_manifest.json"

# Official starting points; add specific scheme pages/PDF URLs as you verify them.
SOURCE_URLS = [
    "https://www.tnagrisnet.tn.gov.in/home/schemes/tm",
    "https://www.tnagrisnet.tn.gov.in/home/gos",
    "https://www.agritech.tnau.ac.in/govt_schemes_services/pdf/govt_serv_schems_policy_notes.html",
    "https://tnhorticulture.tn.gov.in/current-scheme-gos",
]
MAX_PDFS = 100
MAX_PAGES = 20
TIMEOUT_MS = 25000

def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def save_pdf(url: str, session: requests.Session):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    path = DOWNLOADS / f"{digest}.pdf"
    if not path.exists():
        try:
            response = session.get(url, timeout=30, headers={"User-Agent": "TamilNaduAgricultureSchemeResearchBot/1.0"})
            response.raise_for_status()
            if "pdf" not in response.headers.get("content-type", "").lower() and not url.lower().split("?")[0].endswith(".pdf"):
                return None
            path.write_bytes(response.content)
        except Exception as exc:
            print(f"[WARN] PDF download failed: {url} ({exc})")
            return None
    return path

def extract_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            content = clean(page.extract_text() or "")
            if content:
                pages.append(f"[PDF page {i}]\n{content}")
        return "\n\n".join(pages)
    except Exception as exc:
        print(f"[WARN] Could not extract {path.name}: {exc}")
        return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Replace the saved corpus and source manifest")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    if CORPUS.exists() and SOURCES.exists() and MANIFEST.exists() and not args.rebuild:
        print("Corpus already exists. Skipping ingestion. Use --rebuild to intentionally refresh it.")
        return

    pages_to_visit = list(dict.fromkeys(SOURCE_URLS))
    seen_pages, seen_pdfs, records = set(), set(), []
    session = requests.Session()
    text_blocks = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        while pages_to_visit and len(seen_pages) < MAX_PAGES:
            url = pages_to_visit.pop(0)
            if url in seen_pages:
                continue
            seen_pages.add(url)
            print(f"[PAGE] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                page.wait_for_timeout(1000)
                title = page.title()
                page_text = clean(page.locator("body").inner_text(timeout=8000))
                if len(page_text) > 80:
                    text_blocks.append(f"SOURCE: {url}\nTITLE: {title}\nTYPE: webpage\n\n{page_text}")
                    records.append({"url": url, "title": title, "type": "webpage"})
                links = page.locator("a").evaluate_all("""els => els.map(a => ({
                    href: a.href || '', text: (a.innerText || a.textContent || '').trim()
                }))""")
                for link in links:
                    href = link.get("href", "")
                    if not href.startswith("http"):
                        continue
                    if href.lower().split("?")[0].endswith(".pdf") and href not in seen_pdfs and len(seen_pdfs) < MAX_PDFS:
                        seen_pdfs.add(href)
                    elif urlparse(href).netloc == urlparse(url).netloc and href not in seen_pages and len(pages_to_visit) < MAX_PAGES:
                        # Follow a small number of same-domain links, prioritizing scheme/policy/G.O. pages.
                        hint = (link.get("text", "") + " " + href).lower()
                        if any(word in hint for word in ["scheme", "policy", "go", "citizen", "agri", "hort", "farmer", "thittam"]):
                            pages_to_visit.append(href)
            except Exception as exc:
                print(f"[WARN] Page failed: {url} ({exc})")
        browser.close()

    for url in sorted(seen_pdfs):
        print(f"[PDF] {url}")
        path = save_pdf(url, session)
        if not path:
            continue
        content = extract_pdf(path)
        if content:
            text_blocks.append(f"SOURCE: {url}\nTITLE: {path.name}\nTYPE: pdf\n\n{content}")
            records.append({"url": url, "title": path.name, "type": "pdf", "local_file": str(path.relative_to(ROOT))})

    CORPUS.write_text("\n\n" + ("\n\n" + "=" * 90 + "\n\n").join(text_blocks), encoding="utf-8")
    SOURCES.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_pages_visited": len(seen_pages),
        "pdf_links_found": len(seen_pdfs),
        "documents_extracted": len(records),
        "note": "Review corpus and manifest; automated extraction may miss content or include irrelevant page text."
    }, indent=2), encoding="utf-8")
    print(f"Saved corpus: {CORPUS}")
    print(f"Saved source manifest: {SOURCES}")
    print(f"Extracted {len(records)} source documents. Review them before building the index.")

if __name__ == "__main__":
    main()
