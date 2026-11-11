import json
import os
from pathlib import Path
from typing import List, Dict

import requests
from dotenv import load_dotenv
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

for env_file in (BASE_DIR / ".env", DATA_DIR / ".env"):
    if env_file.exists():
        load_dotenv(env_file)

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"


def get_client():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Ollama is not running or not available. Start Ollama first with: 'ollama run llama3'"
        ) from exc

    return {"url": OLLAMA_URL, "model": MODEL_NAME}


def extract_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    text_chunks = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_chunks.append(page_text)
    return "\n".join(text_chunks)


def load_documents(folder: Path = DATA_DIR) -> List[Dict[str, str]]:
    documents: List[Dict[str, str]] = []

    if not folder.exists():
        raise FileNotFoundError(f"Data folder not found: {folder}")

    for file_path in sorted(folder.iterdir()):
        if file_path.is_dir():
            continue

        if file_path.suffix.lower() == ".pdf":
            text = extract_pdf_text(file_path)
        elif file_path.suffix.lower() in {".txt", ".md"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            continue

        if text.strip():
            documents.append({"source": file_path.name, "text": text})

    if not documents:
        raise FileNotFoundError(
            f"No supported documents found in {folder}. Add a .txt, .md or .pdf file first."
        )

    return documents


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap

    return chunks


def build_index(documents: List[Dict[str, str]], top_k: int = 3):
    chunks = []
    for doc in documents:
        for chunk in chunk_text(doc["text"]):
            chunks.append({"source": doc["source"], "text": chunk})

    if not chunks:
        raise ValueError("No text chunks were created from the supplied documents.")

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([chunk["text"] for chunk in chunks])
    return vectorizer, matrix, chunks, top_k


def retrieve_context(query: str, vectorizer, matrix, chunks: List[Dict[str, str]], top_k: int = 3):
    query_vector = vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, matrix).flatten()
    top_indices = similarities.argsort()[-top_k:][::-1]

    selected = [chunks[i] for i in top_indices if similarities[i] > 0]
    if not selected:
        return "No relevant content found in the uploaded documents."

    context_parts = []
    for item in selected:
        context_parts.append(f"Source: {item['source']}\n{item['text']}")
    return "\n\n---\n\n".join(context_parts)


def ask_rag_chatbot(query: str):
    documents = load_documents(DATA_DIR)
    vectorizer, matrix, chunks, top_k = build_index(documents)
    context = retrieve_context(query, vectorizer, matrix, chunks, top_k)

    system_prompt = (
        "You are a helpful assistant. Answer the user's question using only the context below. "
        "If the answer is not in the context, say: 'I could not find this information in the uploaded documents.'"
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    client = get_client()
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"

    payload = {
        "model": client["model"],
        "prompt": combined_prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    response = requests.post(client["url"], json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")


if __name__ == "__main__":
    try:
        while True:
            question = input("Ask a question about your documents (or type 'exit' to quit): ").strip()
            if not question:
                continue
            if question.lower() in {"exit", "quit", "q"}:
                print("Goodbye!")
                break

            answer = ask_rag_chatbot(question)
            print("\nAnswer:\n")
            print(answer)
            print("\n" + "-" * 60)
    except KeyboardInterrupt:
        print("\nSession ended by user.")
