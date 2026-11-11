# bittu_RAG_chatbot

A document-question-answering app that retrieves relevant text from your PDF, TXT, and Markdown files, then uses a locally running Ollama model to generate an answer. No paid API key is required.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running
- The `llama3` model downloaded in Ollama

## Run on Windows

Open PowerShell in this project folder and run:

```powershell
ollama pull llama3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000> in your browser. Upload PDF, TXT, or Markdown documents in the sidebar and ask questions in the chat.

Uploaded files are saved in `data/`. That folder is excluded from Git because documents may contain private information. Add your own files through the app after setting it up.

## Sign-in setup

Add these settings to your local `.env` file. Keep any existing lines in that file, and choose your own username and a long, unique password:

```dotenv
APP_USERNAME=your_username
APP_PASSWORD=your_long_unique_password
FLASK_SECRET_KEY=your_random_secret
```

Generate a random session secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into `FLASK_SECRET_KEY`. The `.env` file is excluded from Git.

## GitHub and hosting

GitHub stores this project's source code; it does not run the Python app or Ollama model. The app currently connects to Ollama on the same machine at `http://localhost:11434`, so it works locally. To make it available online, deploy the Python app and an Ollama service on a server, then configure access securely. Do not expose Flask's development server directly to the public internet. This simple single-user sign-in is intended for local use, not as a substitute for production identity management.

## Current limitations

- The retrieval index is built in memory and rebuilt for each question. Large document collections will need a persistent vector database and an embedding-based index.
- PDFs must contain selectable text; scanned PDFs need OCR before their text can be retrieved.
- Ollama speed and model quality depend on the machine running the model.
