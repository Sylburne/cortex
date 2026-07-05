# QMind Deployment Guide — Render + Neon (10 minutes)

## Prerequisites
- [Neon account](https://neon.tech) (free, 0.5GB Postgres + pgvector)
- [Render account](https://render.com) (free, 512MB web service)
- OpenAI API key (or Anthropic/Ollama)
- Optional: [Honcho account](https://app.honcho.dev) ($100 free credits for AI memory)

## Step 1: Create Neon Database (2 min)

1. Go to [neon.tech](https://neon.tech) → New Project
2. Name it `qmind` → Create Project
3. Copy the **connection string** (looks like: `postgresql://user:pass@ep-xxx.aws.neon.tech/qmind?sslmode=require`)
4. In the Neon SQL editor, run:
   ```sql
   CREATE EXTENSION vector;
   ```

## Step 2: Deploy to Render (5 min)

1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo (or upload the `qmind/backend` folder)
3. Configure:
   - **Name**: `qmind-api`
   - **Environment**: `Python 3`
   - **Region**: Oregon (or closest to you)
   - **Plan**: Free
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`

4. Add Environment Variables:
   ```
   DATABASE_URL=postgresql://user:pass@ep-xxx.aws.neon.tech/qmind?sslmode=require
   API_KEY=your-strong-random-key-here
   OPENAI_API_KEY=sk-xxx
   EMBEDDING_PROVIDER=openai
   EMBEDDING_MODEL=text-embedding-3-small
   DEFAULT_LLM_PROVIDER=openai
   DEFAULT_LLM_MODEL=gpt-4o
   ```

   **Optional — Enable Honcho Memory:**
   ```
   HONCHO_API_KEY=your-honcho-key
   HONCHO_WORKSPACE_ID=qmind
   ```

5. Click **Create Web Service**

## Step 3: Verify Deployment (1 min)

Wait for Render to finish deploying (~2-3 min), then:

```bash
python verify_deploy.py https://qmind-api.onrender.com
```

You should see:
```
✓ Root endpoint                 200 (expected 200)
  Service: qmind | Version: 0.1.0
  Honcho: enabled
✓ Health endpoint               200 (expected 200)
✓ Create notebook               200 (expected 200)
✓ List notebooks                200 (expected 200)
✓ Get notebook                  200 (expected 200)
✓ Memory status                 200 (expected 200)
```

## Step 4: Test with CLI

```bash
cd qmind/cli
go build -o qmind-local
./qmind-local login
./qmind-local notebook create "My First Notebook"
./qmind-local notebook list
```

## What You Get

**Base Version (no Honcho):**
- Notebook CRUD
- Document upload with auto parse→chunk→embed
- Vector search (pgvector)
- RAG Q&A with citations
- Knowledge compilation
- Linting

**Honcho Version (add HONCHO_API_KEY):**
- Everything above, PLUS:
- Persistent user memory across sessions
- AI learns your preferences over time
- Session context summaries
- User insights API: `POST /api/v1/memory/insights`

## API Endpoints

```
GET  /                           → Service info
GET  /health                     → Health check

POST /api/v1/notebooks           → Create notebook
GET  /api/v1/notebooks           → List notebooks
GET  /api/v1/notebooks/{id}      → Get notebook
DELETE /api/v1/notebooks/{id}    → Delete notebook

POST /api/v1/notebooks/{id}/sources        → Upload file (auto-chunks & embeds)
GET  /api/v1/notebooks/{id}/sources        → List sources
DELETE /api/v1/notebooks/{id}/sources/{id} → Delete source

POST /api/v1/notebooks/{id}/search         → Vector search
POST /api/v1/notebooks/{id}/retrieve       → Semantic retrieval

POST /api/v1/notebooks/{id}/rag/sessions   → Create RAG session
POST /api/v1/notebooks/{id}/rag/sessions/{sid}/messages → Send message, get RAG answer

GET  /api/v1/memory/status       → Check Honcho status
POST /api/v1/memory/insights     → Query user insights (Honcho)
POST /api/v1/memory/context      → Get session context (Honcho)
```

## Troubleshooting

**Service won't start:**
- Check Render logs for missing env vars
- Verify DATABASE_URL uses `postgresql://` (not `postgres://`)

**pgvector errors:**
- Run `CREATE EXTENSION vector;` in Neon SQL editor
- The app tries to auto-create it on startup

**Upload succeeds but search fails:**
- Wait 5-10 seconds for background processing (parse→chunk→embed)
- Check source status: `GET /api/v1/notebooks/{id}/sources` → look for `status: "ready"`

**Honcho not working:**
- Verify HONCHO_API_KEY is set in Render env vars
- Check `GET /api/v1/memory/status` → should show `enabled: true`
- Honcho failures don't break the app (graceful degradation)

## Cost

| Service | Free Tier | Your Cost |
|---------|-----------|-----------|
| Render | 512MB web service | $0 |
| Neon | 0.5GB storage | $0 |
| OpenAI | Pay per token | ~$0.01-0.10/query |
| Honcho | $100 credits | $0 (initial) |

**Total: $0 hosting + your AI API keys**

## Next Steps

- Build the Go CLI (needs Go installed)
- Upload your Project Aeon-S documents
- Start asking questions with RAG
- Enable Honcho for persistent memory
