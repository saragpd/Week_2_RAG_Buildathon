import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="விவசாய நண்பன் | Agri Scheme Assistant", page_icon="🌾", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', 'Noto Sans Tamil', sans-serif;
}
.stApp {
    background: linear-gradient(180deg, #f5f8ef 0%, #ffffff 48%, #f8faf4 100%);
}
.block-container {
    max-width: 1050px;
    padding-top: 1.5rem;
    padding-bottom: 7rem;
}

/* Floating agriculture-themed hero header */
.hero {
    background: linear-gradient(120deg, #164e32, #2f7547);
    color: white;
    padding: 1.7rem 2rem;
    border-radius: 22px;
    box-shadow: 0 12px 35px rgba(28, 76, 43, 0.14);
    animation: heroFloat 3s ease-in-out infinite;
}
.hero h1 {
    margin: 0;
    font-size: 2rem;
    color: white;
}
.hero p {
    margin: .5rem 0 0 0;
    opacity: .92;
}
@keyframes heroFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
}

/* Scheme-category pills */
.pill {
    display: inline-block;
    background: #e6f1df;
    color: #245b36;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: .8rem;
    margin: 3px 4px 3px 0;
}
.small-muted {
    color: #647367;
    font-size: .9rem;
}

/* Bottom-centered chat box with soft pulsing green glow */
div[data-testid="stChatInput"] {
    position: fixed;
    bottom: 1.2rem;
    left: 50%;
    transform: translateX(-50%);
    width: min(760px, 88vw);
    z-index: 999;
    background: #fff;
    border-radius: 18px;
    animation: chatGlow 2.5s ease-in-out infinite;
}
@keyframes chatGlow {
    0%, 100% { box-shadow: 0 0 8px rgba(47, 117, 71, .15); }
    50% { box-shadow: 0 0 22px rgba(47, 117, 71, .35); }
}

/* Smooth entrance for chat messages */
div[data-testid="stChatMessage"] {
    border-radius: 16px;
    animation: messageAppear .45s ease-out both;
}
@keyframes messageAppear {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Hover motion for suggested-question buttons */
.stButton > button {
    transition: transform .2s ease, box-shadow .2s ease;
}
.stButton > button:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 16px rgba(47, 117, 71, .2);
}

/* Accessibility: respect reduced-motion preferences */
@media (prefers-reduced-motion: reduce) {
    .hero,
    div[data-testid="stChatInput"],
    div[data-testid="stChatMessage"] {
        animation: none !important;
    }
    .stButton > button {
        transition: none !important;
    }
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🌾 விவசாய நண்பன்")
    st.caption("Tamil Nadu Agriculture Scheme Assistant")
    st.markdown("---")
    st.markdown("### What you can ask")
    st.markdown("- Scheme eligibility\n- Subsidy and benefits\n- Required documents\n- Application process\n- Tamil or English questions")
    st.markdown("---")
    st.caption("Answers are grounded in the locally indexed official documents. Verify time-sensitive details with the department.")

st.markdown("""
<div class="hero">
  <h1>🌾 விவசாய நண்பன்</h1>
  <p>Your Tamil Nadu agriculture scheme assistant</p>
  <p>Find scheme benefits, eligibility, documents, and application guidance — in Tamil or English.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("")
cols = st.columns(3)
with cols[0]:
    st.markdown('<div class="pill">🌱 Agriculture schemes</div>', unsafe_allow_html=True)
with cols[1]:
    st.markdown('<div class="pill">💧 Irrigation & subsidies</div>', unsafe_allow_html=True)
with cols[2]:
    st.markdown('<div class="pill">📄 Official-source answers</div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🌾" if msg["role"] == "assistant" else "🧑‍🌾"):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Official sources"):
                for source in msg["sources"]:
                    st.markdown(f"**{source['title']}**  \n[{source['url']}]({source['url']})")
                    if source.get("excerpt"):
                        st.caption(source["excerpt"])

if not st.session_state.messages:
    st.markdown("### Try asking")
    examples = [
        "What documents are needed for PM-KISAN?",
        "சிறு விவசாயிகளுக்கு என்ன மானியத் திட்டங்கள் உள்ளன?",
        "Explain the Micro Irrigation Scheme eligibility.",
    ]
    excols = st.columns(len(examples))
    for i, example in enumerate(examples):
        with excols[i]:
            if st.button(example, use_container_width=True):
                st.session_state.pending_question = example
                st.rerun()

question = st.chat_input("Ask about an agriculture scheme… / விவசாயத் திட்டம் பற்றி கேளுங்கள்")
if not question and st.session_state.get("pending_question"):
    question = st.session_state.pop("pending_question")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑‍🌾"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="🌾"):
        with st.spinner("Searching the local scheme knowledge base…"):
            try:
                response = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=90)
                response.raise_for_status()
                data = response.json()
                answer = data["answer"]
                sources = data.get("sources", [])
            except requests.RequestException as exc:
                answer = f"Could not reach the RAG API at `{API_URL}`. Start FastAPI and confirm the FAISS index is built.\n\nDetails: {exc}"
                sources = []
        st.markdown(answer)
        if sources:
            with st.expander("Official sources"):
                for source in sources:
                    st.markdown(f"**{source['title']}**  \n[{source['url']}]({source['url']})")
                    if source.get("excerpt"):
                        st.caption(source["excerpt"])
    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
