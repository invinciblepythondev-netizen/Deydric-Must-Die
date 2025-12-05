# Deydric Must Die

A turn-based text adventure game with AI-generated content, set in a dark fantasy/gothic world where characters have rich personalities, complex relationships, and realistic injuries.

## Overview

Deydric Must Die uses LLMs (Claude, GPT) to dynamically generate character actions and dialogue based on deep character profiles, memories, and relationships. The game features:

- **Turn-based gameplay** with randomized character order
- **Realistic injury system** - no HP bars, wounds are specific and can be fatal
- **Rich character psychology** - private thoughts, motivations, secrets, changing relationships
- **Hybrid memory system** - working memory + semantic search + relationship graphs
- **Multiple LLM providers** - Anthropic Claude and OpenAI for flexibility
- **Dark fantasy setting** - no magic, herbalism, medieval-inspired gothic atmosphere

## Quick Start

### Prerequisites
- Python 3.11+
- API keys for Anthropic and OpenAI
- PostgreSQL database (Neon recommended)

### Installation

```bash
# 1. Navigate to project directory
cd "C:\Users\BunsF\Game Dev\Deydric Must Die"

# 2. Activate virtual environment
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env
# Edit .env with your API keys

# 5. Test connections
python scripts/test_all_apis.py
```

See **[SETUP.md](SETUP.md)** for detailed setup instructions.

## Documentation

- **[SETUP.md](SETUP.md)** - Quick start (30 min) + detailed API platform setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture and design decisions
- **[CLAUDE.md](CLAUDE.md)** - Guidance for Claude Code when working on this project
- **[CONTEXT_GUIDE.md](CONTEXT_GUIDE.md)** - Context management and optimization
- **[PROVIDER_FALLBACK_GUIDE.md](PROVIDER_FALLBACK_GUIDE.md)** - LLM provider fallback system

## Technology Stack

### Core
- **Python 3.11+** - Main language
- **Flask** - Web framework
- **SQLAlchemy** - ORM for database

### Data Storage
- **PostgreSQL (Neon)** - Primary database for game state
- **Chroma** → **Pinecone** - Vector database for semantic memory search
- **NetworkX** - Relationship graphs

### AI/LLM
- **Anthropic Claude 3.5 Sonnet** - Character action generation
- **Claude Haiku** - Memory summarization
- **OpenAI text-embedding-3-small** - Semantic embeddings
- **OpenAI GPT-4/3.5** - Alternative LLM provider

## Architecture Highlights

### Memory System
Three-tiered approach for context-rich LLM prompts:

1. **Working Memory** (last 10 turns) - Full detail in PostgreSQL
2. **Short-Term Memory** (session summaries) - Compressed narratives
3. **Long-Term Memory** (all significant events) - Semantic search via vector DB

Plus a **Relationship Graph** tracking trust/fear/respect between characters.

### Injury System
Realistic wounds instead of HP:
- Location-specific injuries (head, torso, limbs)
- Wound types: cuts, stabs, blunt trauma, infections
- Deterioration over time (bleeding, infection, death)
- Treatment requires skill checks
- No magic - only herbalism and medieval medicine

### Turn-Based Game Loop
1. Randomize character order each round
2. For each character:
   - Assemble context from all memory tiers
   - Generate 4-6 action options via LLM
   - Player chooses (if player character) or AI decides
   - Execute action, update state, relationships, wounds
3. Check wound deterioration
4. Advance turn counter

## Development Roadmap

### Phase 1: MVP Prototype (Weeks 1-2)
- [x] Project setup and API configuration
- [ ] Flask app skeleton
- [ ] Database schema and models
- [ ] 2 locations, 3 characters (1 player, 2 AI)
- [ ] Basic turn-based game loop
- [ ] LLM action generation
- [ ] Simple web UI

### Phase 2: Core Features (Weeks 3-4)
- [ ] Relationship tracking
- [ ] Basic injury system
- [ ] Movement between rooms
- [ ] Working memory queries
- [ ] Short-term summarization

### Phase 3: Enhanced Memory (Weeks 5-6)
- [ ] Vector database integration (Chroma)
- [ ] Semantic memory search
- [ ] Long-term memory consolidation
- [ ] Improved context assembly

### Phase 4: Rich Gameplay (Future)
- [ ] Full injury system with deterioration
- [ ] Combat mechanics
- [ ] Skill checks
- [ ] More locations and characters
- [ ] Admin dashboard
- [ ] Save/load games

## Character Profile System

Each character has:

**Core Identity**
- Name, backstory, physical appearance
- Role/responsibilities, social class
- Speech style, education level

**Psychology**
- Personality traits, motivations (short & long-term)
- Current emotional state
- Secrets (never directly revealed)
- Vices, virtues, past traumas

**Knowledge & Skills**
- Skills (combat, medical, persuasion, etc.)
- Superstitions, hobbies
- Preferences (food, clothing, activities, places)

**Physical State**
- Current location, stance (standing, sitting, etc.)
- Inventory (items carried)
- Wounds (separate table with deterioration)
- Fatigue, hunger

**Social**
- Relationships with other characters (trust/fear/respect)
- Reputation with factions
- Opinions of others (dynamic, can change)

## Cost Estimates

**Development Phase** (~100 turns):
- Neon PostgreSQL: **$0** (free tier)
- Anthropic (Claude): **~$4** (with Sonnet)
- OpenAI (embeddings): **~$0.01**
- Chroma: **$0** (local)
- **Total: ~$4-5 per 100 turns**

**Optimized Production**:
- Use Haiku for simple actions
- Cache repeated prompts
- **Estimated: $1-2 per 100 turns**

## Contributing

This is currently a solo development project. Guidelines for future contributors:

1. Read `ARCHITECTURE.md` to understand the system design
2. Check `CLAUDE.md` for coding conventions
3. Run tests before submitting changes: `pytest`
4. Follow the existing code structure

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_character.py

# Run with coverage
pytest --cov=app tests/
```

## License

[To be determined]

## Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/) and [OpenAI](https://openai.com/)
- Database hosted on [Neon](https://neon.tech/)
- Vector search powered by [Chroma](https://www.trychroma.com/)

---

**Status**: 🚧 In Development - MVP Phase

For questions or issues, see the documentation files listed above.
