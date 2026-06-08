# NewsCheck AI 🔍

NewsCheck AI is an advanced, production-ready, AI-powered fact-checking and news verification platform. It automates the process of identifying factual claims in articles, social media posts, or general text, searching the web and trusted fact-checking organizations for validation, indexing evidence in an in-memory RAG database (FAISS), evaluating the credibility of the sources, performing bias & tone analysis, and delivering a final explainable report with a credibility score.

## Key Features (Resume-Worthy Enhancements)
1. **Multi-Agent Workflow (LangGraph)**: Orchestrated using LangGraph to connect specialized agent nodes (Extraction, Claims, Search, RAG, Verification, Bias, Report).
2. **Conditional Agent Routing**: If the verification agent detects a lack of evidence resulting in an "UNVERIFIED" status, it dynamically routes back to perform a **Deep Search** with expanded queries.
3. **Fact-Checker Prioritization**: First queries trusted fact-check agencies (Snopes, PolitiFact, FactCheck.org) before performing general web searches.
4. **Source Credibility & Weighting**: A database of major domains and their credibility scores is maintained. Retrieved evidence is weighted and scored based on both semantic relevance and source reliability.
5. **Asynchronous Parallel Processing**: Speeds up verification times up to 5x using `asyncio.gather` for concurrent web searches and claim validations.
6. **SQLite-Backed Caching**: Caches search engine results and LLM outputs to significantly reduce cost and latency.
7. **Bias & Sentiment Analysis**: A dedicated agent inspects articles for political leaning (Left, Center, Right) and emotional tone (Neutral, Sensational, Fear-inducing).
8. **Asynchronous Job Queue**: A background task worker pattern managed via FastAPI `BackgroundTasks`. The UI polls status to avoid request timeouts during complex, multi-agent operations.
9. **Evaluation Harness**: An automated evaluation framework that compares agent verdicts against a ground truth dataset, computing Precision, Recall, F1, and Accuracy.
10. **Modern Tech Stack**: FastAPI, Streamlit, LangGraph, FAISS, Plotly, Docker, SQLite.

---

## Architecture Flow
```
                 [ User Input: URL or Text ]
                              │
                    ┌─────────▼─────────┐
                    │ Article Extractor │ (BS4 & LLM Summary)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Claim Extractor  │ (Isolates 1-5 claims)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Search Agent    │ <──────────────┐
                    └─────────┬─────────┘                │
                              │                          │
                    ┌─────────▼─────────┐                │
                    │Evidence Retrieval │ (FAISS RAG &   │ (If Insufficient Evidence
                    │    & Scoring      │  Source Trust) │  and Loop Count < 2)
                    └─────────┬─────────┘                │
                              │                          │
                    ┌─────────▼─────────┐                │
                    │   Fact Verifier   │ ───────────────┘ (Conditional Route)
                    └─────────┬─────────┘
                              │ (Sufficient Evidence)
                    ┌─────────▼─────────┐
                    │   Bias Detector   │ (Bias & Tone Analysis)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Report Generator  │ (Calculates Final Score & MD Report)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  SQLite Database  │ (Persists runs, claims & evidence)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │Streamlit Dashboard│ (Visual Analytics & History)
                    └───────────────────┘
```

---

## Getting Started

### Prerequisites
- Python 3.10 or 3.11
- Docker (optional)

### Configuration
1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your keys:
   - `OPENAI_API_KEY`: Your OpenAI API key (or equivalent provider key).
   - If using a local LLM or provider (Ollama, LM Studio, Groq, DeepSeek), uncomment and set `OPENAI_API_BASE` and `OPENAI_MODEL` accordingly.
   - `TAVILY_API_KEY`: Optional, for professional search results (falls back to DuckDuckGo search automatically if blank).

### Option 1: Local Installation (Manual)

1. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the FastAPI Backend:
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```
   *The SQLite database will auto-initialize on startup.*
4. Run the Streamlit Frontend:
   ```bash
   streamlit run frontend/streamlit_app.py
   ```
5. Open your browser to `http://localhost:8501`.

---

### Option 2: Run with Docker Compose (Recommended)

To run the complete system in isolated containers:
```bash
docker-compose up --build
```
- FastAPI Backend: `http://localhost:8000` (API Docs at `http://localhost:8000/docs`)
- Streamlit Frontend: `http://localhost:8501`

---

## Running Evaluations

To test the accuracy, precision, recall, and F1-score of the system against a ground truth dataset, run the following:
```bash
python evaluation/run_eval.py
```
This script will read `evaluation/eval_dataset.json`, execute the full agent pipeline for each item, calculate stats, and write the output report to `evaluation/eval_results.json`.

---

## Project Structure Explained
- `backend/agents/state.py`: Defines what state variables flow between nodes.
- `backend/agents/workflow.py`: Manages the graph creation, state transitions, and loops using LangGraph.
- `backend/services/search_service.py`: Implements Search. It searches specific fact-check domains first, falling back to general search, and handles API keys.
- `backend/services/cache_service.py`: Caches queries to avoid high API latency and cost.
- `backend/rag/faiss_store.py`: Builds a dynamic vector database using FAISS on the fly to support retrieval augmented verification.
- `database/schema.sql`: Contains the relational tables and default credibility ratings for top news agencies.
