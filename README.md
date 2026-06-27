# LandRight v2 — AI Copilot for International Students

LandRight is a full-stack AI assistant that helps international students navigate life in the US — OPT/CPT timelines, banking, taxes, housing, SSN, and more. It answers general questions from its own knowledge and uses RAG + tool calling when personalized data is needed.

## Demo

> Upload your I-20, ask about your OPT deadline, check your task checklist, and get answers grounded in your own documents.

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq (`openai/gpt-oss-120b`) |
| Agent | LangGraph ReAct (`create_react_agent`) |
| Vector DB | Qdrant Cloud (user-scoped RAG) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Backend | FastAPI + async SQLAlchemy + PostgreSQL |
| Auth | JWT + bcrypt |
| PDF Parsing | pdfplumber |
| Frontend | React + Vite + Tailwind CSS |
| Storage | AWS S3 (documents) + SES (email notifications) |
| Scheduler | APScheduler (nightly deadline reminders) |

## Architecture

```
User message
    │
    ▼
Intent Router (regex classifier)
    │
    ├── General question → Direct Groq LLM (fast, no tool overhead)
    │
    └── Personal data / doc question → LangGraph ReAct Agent
            │
            ├── get_user_profile       → PostgreSQL
            ├── calculate_deadlines    → deadline service
            ├── get_pending_tasks      → PostgreSQL
            ├── mark_task_done         → PostgreSQL
            ├── get_user_memory        → PostgreSQL
            ├── update_user_memory     → PostgreSQL
            └── search_docs            → Qdrant (user-scoped)
```

## Features

- **Smart routing** — general immigration questions go directly to the LLM; personal questions (deadlines, tasks, uploaded docs) invoke the ReAct agent with tools
- **User-scoped RAG** — users upload their own documents (I-20, offer letters, DSO instructions, lease agreements); the agent retrieves only their documents
- **Automatic I-20 parsing** — upload your I-20 PDF to auto-fill program end date, SEVIS ID, and university into your profile
- **Deadline calculator** — computes OPT application window, STEM extension eligibility, and tax deadlines from your program end date
- **Persistent memory** — agent remembers facts across conversations (SSN status, bank choice, job offer, etc.)
- **Task checklist** — stage-based checklist (pre-arrival → day 0 → month 1 → ongoing)
- **Nightly notifications** — APScheduler emails deadline reminders via AWS SES
- **Eval dashboard** — admin view for LLM traces, latency, thumbs up/down feedback

## Project Structure

```
landright-v2/
├── backend/
│   ├── agents/
│   │   └── graph.py          # LangGraph ReAct agent + intent router
│   ├── api/                  # FastAPI routers (auth, chat, profile, documents, tasks)
│   ├── core/
│   │   ├── llm.py            # Groq LLM config
│   │   └── config.py         # Pydantic settings
│   ├── db/
│   │   └── qdrant.py         # Qdrant client, upsert, user-scoped search
│   ├── mcp/
│   │   └── tools.py          # 7 LangChain tools for the agent
│   ├── models/               # SQLAlchemy models
│   └── services/             # Deadline calculator, document parser, scheduler
├── frontend/
│   └── src/
│       ├── pages/            # Chat, Dashboard, Login, Onboarding
│       └── components/       # Sidebar
├── scripts/
│   └── ingest.py             # One-time Qdrant collection setup
├── alembic/                  # DB migrations
├── requirements.txt
└── docker-compose.yml
```

## Setup

### Prerequisites
- Python 3.11+
- Node 18+
- PostgreSQL
- Qdrant Cloud account (free tier)
- Groq API key (free tier)

### Backend

```bash
# Clone and set up virtual environment
git clone https://github.com/RishithaReddy-stack/landright-v2.git
cd landright-v2
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in your keys (see .env.example)

# Run migrations
alembic upgrade head

# Start the API
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/landright

GROQ_API_KEY=your-groq-api-key

QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
COLLECTION_NAME=landright_docs

# Optional — for document storage and email notifications
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register |
| POST | `/api/auth/login` | Login (returns JWT) |
| GET/PUT | `/api/profile` | Get/update student profile |
| POST | `/api/chat` | Send message to agent |
| GET | `/api/chat/conversations` | List conversations |
| POST | `/api/documents/upload` | Upload doc to Qdrant |
| POST | `/api/documents/upload-i20` | Parse I-20 + index |
| GET | `/api/documents` | List uploaded docs |
| DELETE | `/api/documents/{filename}` | Remove a doc |
| GET | `/api/tasks` | Get task checklist |
| GET | `/api/admin/traces` | LLM trace logs |

## How the Agent Works

1. User asks a question
2. **Intent router** checks if it needs personal data (`my` keyword → agent, otherwise → direct LLM)
3. If routed to agent: `llama ReAct` decides which tools to call
4. Tools fetch from PostgreSQL or Qdrant and return structured data
5. Agent synthesizes a personalized answer
6. If tool calling fails (Groq format error): grounded fallback runs the search manually and passes results as context to the LLM

## Author

Rishitha Reddy — [GitHub](https://github.com/RishithaReddy-stack)
