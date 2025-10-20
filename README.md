# 🧠 RealEstateAICore
> **NextaOS / Reivesti AI Command Core** — a modular, multi-agent framework that automates property intelligence, scoring, and deal analysis using open and cloud LLMs.

---

## 🚀 Overview

**RealEstateAICore** is the central AI brain powering your real-estate automation stack.  
It connects data from Airtable, runs autonomous agents for scoring, comps, offers, and messaging, and routes tasks to the best language model (local or cloud).

### ✨ Key Features
- 🧩 **Agent Framework** — SMS, Offer, Comps, Score, Trainer, Market-Trends, and more  
- ⚙️ **Smart Model Router** — automatically selects GPT-4o, Claude, Mistral, Phi-3, etc.  
- 📈 **Lead Scoring Engine** — web + API analysis with 24-month sale filter & ZIP metrics  
- 🔄 **Self-Learning Loop** — trainer agent refines weights and decision logic over time  
- 🧠 **Vector & Data Layer** — embeddings, Airtable sync, and searchable memory  
- ☁️ **Local + Cloud Hybrid** — run free open-weight models via Ollama or connect to APIs  

---

## 🗂️ Folder Structure
realestateaicore/
├── agents/
│   ├── sms_agent.py
│   ├── offer_agent.py
│   ├── comps_agent.py
│   ├── score_agent.py
│   ├── trainer_agent.py
│   ├── market_trends_agent.py
│   └── ai_thoughts_agent.py
│
├── api/
│   ├── routes.py
│   └── ai_router.py
│
├── config/
│   ├── models.json
│   ├── weights.json
│   └── env.py
│
├── data/
│   ├── airtable_client.py
│   ├── vector_store.py
│   └── logger.py
│
├── utils/
│   ├── model_selector.py
│   ├── filters.py
│   └── helpers.py
│
├── main.py
└── README.md
---

## 🧰 Requirements

| Component | Purpose | Install |
|------------|----------|----------|
| **Python 3.11+** | Core runtime | `sudo apt install python3` |
| **FastAPI + Uvicorn** | API layer | `pip install fastapi uvicorn` |
| **Airtable** | Data backend | `pip install pyairtable` |
| **LLM Clients** | Model access | `pip install openai anthropic requests python-dotenv` |
| **Ollama (optional)** | Run free local models | [ollama.com/download](https://ollama.com/download) |

---

## ⚙️ Environment Setup

Create a `.env` file in the root:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
AIRTABLE_API_KEY=...
BASE_ID=...
LOCAL_MISTRAL_URL=http://localhost:11434/api/generate

Never commit your real keys; instead include a safe .env.example for reference.

🧠 Model Configuration

Edit config/models.json to choose which model handles each task.
{
  "default": "gpt-4o",
  "summarize": "claude-3-opus",
  "classify": "gpt-4o",
  "extract": "mistral-7b",
  "generate_response": "phi3:mini"
}

To run open-weight models locally:
ollama pull mistral:7b
ollama run mistral:7b

▶️ Run the API
uvicorn main:app --reload --port 8000

Then open:
👉 http://localhost:8000/docs to test endpoints.

Example:
curl -X POST http://localhost:8000/run-agent/score \
     -H "Content-Type: application/json" \
     -d '{"address": "123 Main St, Miami, FL"}'

⸻

🧮 Agents Included
Agent
Role
sms_agent
Handles inbound/outbound messaging
offer_agent
Generates cash or creative offers
comps_agent
Pulls and averages comparable sales
score_agent
Calculates motivation & deal scores (0–100)
trainer_agent
Improves weights & model routing
market_trends_agent
Fetches ZIP-level sales & flip metrics
ai_thoughts_agent
Logs insights and system feedback

⸻

☁️ Deploy Options
Platform
Notes
Local Dev
Ollama + Uvicorn
RunPod / Vast.ai
Always-on GPU micro-server
Render / Railway / Fly.io
FastAPI hosting (free tiers)
Docker
Coming soon: Dockerfile + docker-compose.yml


⸻

🧩 Roadmap
	•	Agent performance dashboard
	•	Integrated Whisper voice agent
	•	Real-time property image analyzer (LLaVA)
	•	Full Notion / Airtable auto-sync
	•	AI-powered offer negotiation module

⸻

🛡️ License

MIT License — feel free to use, modify, and build on it.

⸻

🧠 Built for Operators

This project is engineered for real-estate investors and automation builders who want to scale acquisitions with AI.

Run it. Refine it. Let it close deals while you sleep.
