# Setup Guide

Get "Deydric Must Die" up and running quickly or follow detailed setup instructions.

## Quick Start (30 minutes)

### Prerequisites
- Python 3.11+ installed
- Credit card for API services (minimal charges during development)

### Step 1: Install Dependencies (5 min)
```bash
cd "C:\Users\BunsF\Game Dev\Deydric Must Die"
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Set Up APIs (15 min)

**Neon PostgreSQL:**
1. Sign up at https://neon.tech
2. Create project "deydric-must-die"
3. Copy connection string

**Anthropic API:**
1. Sign up at https://console.anthropic.com
2. Add payment + set $50 monthly limit
3. Create API key

**OpenAI API:**
1. Sign up at https://platform.openai.com
2. Add $10 credit + set $20 monthly limit
3. Create API key

### Step 3: Configure Environment (5 min)
```bash
copy .env.example .env
notepad .env
```

Update these values:
- `FLASK_SECRET_KEY`: Run `python -c "import secrets; print(secrets.token_hex(32))"`
- `NEON_DATABASE_URL`: Paste Neon connection string
- `ANTHROPIC_API_KEY`: Paste Anthropic key
- `OPENAI_API_KEY`: Paste OpenAI key

### Step 4: Test Connections (5 min)
```bash
python scripts/test_all_apis.py
```

Should show all services working. If any fail:
- Check API keys in `.env`
- Verify billing is set up
- Check internet connection

**Done!** Ready for development.

---

## Detailed Setup Instructions

### Service Overview

| Service | Purpose | Cost (Free Tier) | Required |
|---------|---------|------------------|----------|
| Neon PostgreSQL | Primary database | 512MB storage | Yes |
| Anthropic API | Claude LLM | Pay-as-you-go ~$3-15/MTok | Yes |
| OpenAI API | Embeddings + fallback LLM | Pay-as-you-go | Yes |
| Chroma | Vector DB (local) | Free | Optional |

**Estimated monthly cost:** $0 infrastructure + $20-30 LLM usage

---

## Neon PostgreSQL Setup

### Create Account
1. Go to https://neon.tech
2. Sign up with GitHub/Google/email
3. Verify email

### Create Project
1. Click "Create a project"
2. Configure:
   - Name: `deydric-must-die`
   - Region: Choose closest
   - PostgreSQL: 16 (latest)
   - Compute: 0.25 vCPU (free tier)
3. Click "Create Project"

### Get Connection String
1. Find "Connection Details" section
2. Copy the full connection string:
   ```
   postgresql://username:password@host/neondb?sslmode=require
   ```
3. Save this for `.env` file

### Enable Extensions (Optional)
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Cost Management
- Free tier: 512MB storage, 0.5 compute units (~190 hours/month)
- Email warnings before hitting limits
- Upgrade to Pro ($19/mo) only if needed

---

## Anthropic API Setup

### Create Account
1. Go to https://console.anthropic.com
2. Sign up with email/Google
3. Verify email

### Set Up Billing
1. Go to Settings → Billing
2. Add payment method
3. Set monthly spending limit (recommended: $50)
4. Set email alerts at 50% and 80%
5. Get $5 free credit for new accounts

### Generate API Key
1. Go to API Keys section
2. Click "Create Key"
3. Name it: `deydric-dev`
4. Copy immediately (starts with `sk-ant-`)
5. Store securely - you won't see it again

### Pricing
**Claude 3.5 Sonnet** (character actions):
- Input: $3 per million tokens
- Output: $15 per million tokens

**Claude 3.5 Haiku** (summaries):
- Input: $0.25 per million tokens
- Output: $1.25 per million tokens

**Example:** 100 turns ≈ $4-5 with Sonnet

### Rate Limits (Tier 1)
- 50 requests/minute
- 40,000 tokens/minute
- 1,000,000 tokens/day

Plenty for development.

---

## OpenAI API Setup

### Create Account
1. Go to https://platform.openai.com/signup
2. Sign up and complete phone verification

### Set Up Billing
1. Settings → Billing
2. Add payment method
3. Add initial credit (minimum $5)
4. Set monthly budget cap (recommended: $20)
5. Enable email notifications

**Note:** No free credits for new accounts (as of 2024)

### Generate API Key
1. Go to API keys section
2. "Create new secret key"
3. Name: `deydric-dev`
4. Copy (starts with `sk-`)
5. Save immediately

### Pricing
**Text Embedding 3 Small** (semantic search):
- $0.02 per million tokens
- 1536 dimensions

**GPT-4o Mini** (fallback):
- Input: $0.15 per million tokens
- Output: $0.60 per million tokens

### Rate Limits (Tier 1)
- GPT-4o: 500 req/min, 30K tokens/min
- Embeddings: 3,000 req/min, 1M tokens/min

---

## Chroma Vector Database Setup

### Installation
Chroma is a Python library - no account needed!

```bash
# Already installed with requirements.txt
# Verify:
python -c "import chromadb; print('ChromaDB installed')"
```

### Configuration Modes

**Persistent Local (Recommended for Dev):**
```python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
```

**In-Memory (Testing):**
```python
client = chromadb.Client()
```

**Client-Server (Production):**
```bash
chroma run --path ./chroma_db --port 8000
```

### Basic Usage
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

# Create collection
collection = client.get_or_create_collection("character_memories")

# Add document
collection.add(
    documents=["The knight confronted the herbalist."],
    metadatas=[{"character_id": 1, "turn": 42}],
    ids=["memory_1"]
)

# Query
results = collection.query(
    query_texts=["confrontation"],
    n_results=1
)
```

### Directory Structure
```
chroma_db/              # Created automatically
├── chroma.sqlite3      # Metadata
└── [uuid folders]      # Vector data
```

**Add to `.gitignore`:**
```
chroma_db/
*.sqlite3
```

---

## Environment Variables

### Create .env File

```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_SECRET_KEY=your-secret-key-here

# Database (Neon PostgreSQL)
NEON_DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# LLM Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Secondary Providers (optional)
AIMLAPI_API_KEY=your-key-here
TOGETHER_API_KEY=your-key-here

# Vector Database
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Embeddings
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_DIMENSION=1536

# LLM Configuration
PRIMARY_LLM_PROVIDER=anthropic
PRIMARY_LLM_MODEL=claude-3-5-sonnet-20241022
SUMMARY_LLM_MODEL=claude-3-5-haiku-20241022
FALLBACK_LLM_PROVIDER=openai
FALLBACK_LLM_MODEL=gpt-4o-mini

# Application Settings
DEBUG=True
MAX_TURNS_WORKING_MEMORY=10
SUMMARIZE_EVERY_N_TURNS=10
MAX_CONTEXT_TOKENS=15000
```

### Generate Flask Secret Key
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Update .gitignore
```
.env
.env.local
venv/
__pycache__/
chroma_db/
*.sqlite3
*.log
```

---

## Verification Checklist

### Accounts Created
- [ ] Neon PostgreSQL account
- [ ] Anthropic account + billing
- [ ] OpenAI account + billing
- [ ] Chroma installed

### API Keys Obtained
- [ ] Neon connection string saved
- [ ] Anthropic API key (starts with `sk-ant-`)
- [ ] OpenAI API key (starts with `sk-`)
- [ ] All keys added to `.env`
- [ ] `.env` in `.gitignore`

### Services Tested
- [ ] Neon PostgreSQL connection works
- [ ] Anthropic API call succeeds
- [ ] OpenAI embeddings work
- [ ] Chroma creates collections

### Cost Management
- [ ] Anthropic spending limit set
- [ ] OpenAI spending limit set
- [ ] Email alerts configured

---

## Test Script

Run this to verify everything works:

```bash
python scripts/test_all_apis.py
```

Expected output:
```
[OK]   Neon: Working
[OK]   Anthropic: Working
[OK]   OpenAI: Working
[OK]   Chroma: Working

All services configured correctly! Ready to start development.
```

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### "psycopg2.OperationalError"
- Check `NEON_DATABASE_URL` in `.env`
- Verify Neon project is running
- Check internet connection

### "anthropic.AuthenticationError"
- Check `ANTHROPIC_API_KEY` in `.env`
- Verify billing is set up
- Ensure key starts with `sk-ant-`

### "openai.AuthenticationError"
- Check `OPENAI_API_KEY` in `.env`
- Verify account has credit
- Ensure key starts with `sk-`

### Chroma Issues
```bash
# Delete and recreate
rmdir /s chroma_db
python scripts/test_chroma.py
```

---

## Cost Expectations

### Development (First Month)
- Neon: $0 (free tier)
- Anthropic: $10-20 (testing)
- OpenAI: $1-5 (embeddings)
- Chroma: $0 (local)
- **Total: $11-25**

### After Optimization
- ~$5-10 per 100 game turns

---

## Next Steps

Once setup is complete:

1. Initialize database schema:
   ```bash
   python scripts/init_db.py
   ```

2. Seed initial data:
   ```bash
   python scripts/seed_data.py
   ```

3. Run Flask app:
   ```bash
   flask run --debug
   ```
   Visit http://localhost:5000

---

## Additional Resources

- **Neon Docs:** https://neon.tech/docs
- **Anthropic Docs:** https://docs.anthropic.com
- **OpenAI Docs:** https://platform.openai.com/docs
- **Chroma Docs:** https://docs.trychroma.com
- **Project Architecture:** See `ARCHITECTURE.md`
- **Claude Code Guide:** See `CLAUDE.md`
