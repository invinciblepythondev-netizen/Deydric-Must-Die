# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Deydric Must Die** is a turn-based text adventure game built with Python Flask. The game features LLM-generated content for dynamic character interactions, set in a dark fantasy/gothic world with realistic injury mechanics and complex character relationships.

### Key Characteristics
- **No magic system** - but herbalism/medicine that some characters perceive as magic
- **Realistic injuries** - no HP bars; wounds are location-specific, can bleed, get infected, and be fatal
- **Rich character psychology** - private thoughts, changing relationships, detailed memories
- **Turn-based gameplay** - randomized turn order, all characters (AI and player) take one action per turn
- **Context-heavy LLM prompts** - hybrid memory system (working memory + semantic search + relationship graphs)

## Architecture

See `ARCHITECTURE.md` for comprehensive technical details. Key points:

### Data Storage
- **PostgreSQL (Neon)**: Primary database for game state, character profiles, locations, turn history, wounds
- **Vector Database** (Qdrant): Cloud-hosted semantic memory search via embeddings
- **NetworkX**: In-memory relationship graphs, serialized to PostgreSQL JSONB

### LLM Providers

**Primary Providers (Quality-First):**
- **Anthropic Claude 3.5 Sonnet**: Primary character action generation
- **Claude Haiku**: Memory summarization, quick decisions
- **OpenAI GPT-4/3.5**: Alternative provider for action generation

**Secondary Providers (Permissive Fallback):**
- **AIML API (api.aimlapi.com)**: Mistral 7B, Mixtral 8x7B, Llama 3 70B/405B - most cost-effective
- **Together.ai**: Mixtral, Llama 3 70B - backup for mature content
- **Local Models**: Llama 3 70B - for unrestricted content (requires GPU)

**Provider Abstraction:**
- Provider abstraction layer allows swapping models
- **Automatic fallback system** for content policy violations
- Content intensity classification (mild → moderate → mature → unrestricted)
- Prompt adaptation per provider's guidelines

### Content Policy Handling

Dark fantasy themes (violence, moral ambiguity, death) may trigger content filters. The system handles this via:

1. **Content Classification**: Automatically detect intensity level
2. **Provider Chain**: Build fallback list of capable providers
3. **Auto-Retry**: If provider refuses, try next in chain
4. **Prompt Adaptation**: Adjust wording per provider
5. **Local Fallback**: Use local models for truly unrestricted content

**See `PROVIDER_FALLBACK_GUIDE.md` for detailed documentation.**

**Configuration:**
- Edit `config_providers.py` to set provider priorities
- Set API keys in `.env`
- Enable local models for unrestricted content (optional)

### Memory System
1. **Working Memory**: Last 10 turns, full detail (PostgreSQL)
2. **Short-Term Memory**: Summarized session history (PostgreSQL)
3. **Long-Term Memory**: Embedded significant events (Vector DB)
4. **Relationship Graph**: Character connections with trust/fear/respect metrics (NetworkX)

## Database Conventions

### Table Naming
- **Singular names only**: `character` (not `characters`), `location` (not `locations`)
- **ID columns**: Named as `tablename_id` (e.g., `character_id`, `location_id`)
- **ID types**:
  - **UUID**: For user-facing or security-sensitive tables where enumeration attacks are a concern
  - **Integer**: For internal relationships and low-risk tables

### Schema Organization
Tables and procedures should be organized into appropriate schemas:
- `game`: Core game state tables
- `character`: Character-related tables
- `world`: Locations, items, environmental data
- `memory`: Turn history, summaries, embeddings

### Stored Procedures
**All database operations must use stored procedures** - no direct table access from application code.

Procedure naming convention:
- `tablename_get` - Retrieve records
- `tablename_upsert` - Insert or update records
- `tablename_delete` - Delete records
- `tablename_list` - Get multiple records with filtering

Examples:
```sql
-- Character operations
character_get(character_id UUID)
character_upsert(character_id UUID, name TEXT, backstory TEXT, ...)
character_delete(character_id UUID)
character_list_by_location(location_id UUID)

-- Location operations
location_get(location_id INTEGER)
location_upsert(location_id INTEGER, name TEXT, description TEXT, ...)

-- Relationship operations
character_relationship_upsert(source_character_id UUID, target_character_id UUID, trust FLOAT, ...)
character_relationship_get(source_character_id UUID, target_character_id UUID)
```

### Application Code Pattern
```python
# Good - using stored procedure
result = db.execute(
    "SELECT * FROM character_get(:id)",
    {"id": character_id}
)

# Bad - direct table access
result = db.execute(
    "SELECT * FROM character WHERE character_id = :id",
    {"id": character_id}
)
```

### SQLAlchemy Models
Models should be **thin wrappers** that call stored procedures, not full ORM entities:

```python
# models/character.py
class Character:
    @staticmethod
    def get(character_id):
        """Retrieve character via stored procedure."""
        result = db.session.execute(
            text("SELECT * FROM character_get(:id)"),
            {"id": character_id}
        ).fetchone()
        return result

    @staticmethod
    def upsert(character_id, name, backstory, **kwargs):
        """Create or update character via stored procedure."""
        db.session.execute(
            text("""
                SELECT character_upsert(
                    :character_id, :name, :backstory, :personality_traits,
                    :motivations_short_term, :motivations_long_term, ...
                )
            """),
            {
                "character_id": character_id,
                "name": name,
                "backstory": backstory,
                **kwargs
            }
        )
        db.session.commit()

    @staticmethod
    def list_by_location(location_id):
        """Get all characters at a location."""
        results = db.session.execute(
            text("SELECT * FROM character_list_by_location(:location_id)"),
            {"location_id": location_id}
        ).fetchall()
        return results
```

**Advantages of this approach:**
- Database logic stays in PostgreSQL (better performance, easier to optimize)
- Security: procedures can enforce business rules and permissions
- Testing: procedures can be tested independently with SQL
- Flexibility: swap between different procedure implementations without code changes

## Migration Workflow

### Initial Setup (First Time)

```bash
# 1. Ensure environment variables are set
# Check your .env file has NEON_DATABASE_URL

# 2. Run database initialization
python scripts/init_db.py
```

This creates:
- Migration tracking table (`public.schema_migration`)
- All schemas (game, character, world, memory)
- All tables
- All stored procedures

### Adding a New Table or Column (Schema Change)

**Option A: Modify existing schema file (before initial deployment)**
```bash
# 1. Edit the schema file
# Example: database/schemas/002_character_schema.sql

# 2. Reset and reinitialize (DEVELOPMENT ONLY)
python scripts/reset_db.py

# This drops everything and recreates from scratch
```

**Option B: Create a migration file (preferred for production)**
```bash
# 1. Create a new migration file with sequential number
# database/migrations/001_add_character_fatigue.sql

# Example migration content:
ALTER TABLE character.character
ADD COLUMN IF NOT EXISTS fatigue_level INTEGER DEFAULT 0 CHECK (fatigue_level >= 0 AND fatigue_level <= 100);

COMMENT ON COLUMN character.character.fatigue_level IS 'Physical exhaustion level 0-100';

# 2. Apply the migration
python scripts/migrate_db.py

# 3. Update the base schema file to match
# Edit database/schemas/002_character_schema.sql to include the new column
# This ensures fresh installs have the correct schema
```

### Updating Stored Procedures

Procedures can be updated without migrations:

```bash
# 1. Edit procedure file
# Example: database/procedures/character_procedures.sql

# 2. Re-run init script (procedures use CREATE OR REPLACE)
python scripts/init_db.py

# Or apply directly with psql
psql $NEON_DATABASE_URL -f database/procedures/character_procedures.sql
```

Since procedures use `CREATE OR REPLACE FUNCTION`, they can be updated without migrations.

### Migration File Naming Convention

```
database/migrations/NNN_description.sql

Examples:
001_add_character_fatigue.sql
002_add_wound_infection_tracking.sql
003_create_faction_tables.sql
```

- **NNN**: 3-digit sequential number (001, 002, 003...)
- **description**: Snake_case description of the change
- **Never modify** a migration file after it's been applied to any environment
- Each migration file is checksummed to detect modifications

### Migration Commands

```bash
# Apply all pending migrations
python scripts/migrate_db.py

# List migration status
python scripts/migrate_db.py --list

# Dry run (see what would be applied)
python scripts/migrate_db.py --dry-run

# Reset database (DEVELOPMENT ONLY - drops everything)
python scripts/reset_db.py
```

### How Claude Should Handle Schema Changes

When asked to add/modify database structure:

1. **For new tables**:
   - Create migration file: `database/migrations/00X_add_table_name.sql`
   - Update schema file: `database/schemas/00X_appropriate_schema.sql`
   - Create procedures: `database/procedures/table_name_procedures.sql`

2. **For new columns**:
   - Create migration file with `ALTER TABLE ... ADD COLUMN`
   - Update the schema file to match
   - Update affected procedures if needed

3. **For procedure changes**:
   - Edit procedure file directly (no migration needed)
   - Use `CREATE OR REPLACE FUNCTION`

### Example: Adding a New Feature

Let's say you need to add a "reputation system with factions":

```bash
# 1. Create migration for new table
# database/migrations/005_add_faction_reputation.sql
CREATE TABLE IF NOT EXISTS character.faction_reputation (
    reputation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id),
    faction_name TEXT NOT NULL,
    reputation_score INTEGER DEFAULT 0,
    UNIQUE(character_id, faction_name)
);

# 2. Update schema file to include the new table
# Edit database/schemas/002_character_schema.sql
# Add the faction_reputation table definition

# 3. Create procedures
# database/procedures/faction_procedures.sql
CREATE OR REPLACE FUNCTION faction_reputation_get(...)
...

# 4. Apply migration
python scripts/migrate_db.py

# 5. Re-run procedures
python scripts/init_db.py
```

### Migration Safety Rules

1. **Never modify applied migrations** - Create a new migration to fix issues
2. **Always test locally first** - Use reset_db.py freely in development
3. **Migrations are one-way** - No automatic rollback (manual rollback migrations needed)
4. **Schema files are source of truth** - Keep them updated to match migrations
5. **Procedures don't need migrations** - They use CREATE OR REPLACE

### Troubleshooting

**Migration fails mid-way:**
- All changes are rolled back (transactional)
- Fix the SQL error
- Re-run `python scripts/migrate_db.py`

**Schema out of sync:**
- Development: `python scripts/reset_db.py` (nuclear option)
- Production: Create corrective migration

**Procedure syntax error:**
- Fix the procedure file
- Re-run `python scripts/init_db.py`
- Procedures are replaced, not appended

## Database Schema (Key Tables)

- `character`: Full character profiles including personality, skills, motivations, preferences, secrets
- `character_relationship`: Graph edges with trust/fear/respect metrics, interaction history
- `location`: Room descriptions, connections (JSONB), items, environmental properties
- `turn_history`: Every action taken, witnesses, outcomes, embedded for semantic search
- `character_wound`: Specific injuries with body part, severity, bleeding/infection status, treatment history
- `character_inventory`: Items carried by each character
- `memory_summary`: Compressed narrative summaries of turn ranges
- `game_state`: Current turn number, turn order, active game flag

## Development Commands

### Setup
```bash
# Create/activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Unix

# Install dependencies
pip install -r requirements.txt

# Set up environment variables (.env file)
NEON_DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
FLASK_SECRET_KEY=...
FLASK_ENV=development
```

### Running the Application
```bash
# Development server
flask run --debug

# Or with python directly
python app.py
```

### Database Initialization & Migrations
```bash
# Initial database setup
# This script executes all .sql files in database/schemas/ and database/procedures/
python scripts/init_db.py

# Manual procedure updates (during development)
# Run individual procedure files against the database
psql $NEON_DATABASE_URL -f database/procedures/character_procedures.sql

# Schema changes
# Edit the appropriate schema file in database/schemas/
# Then re-run init_db.py or manually apply via psql
```

**Note**: This project uses stored procedures instead of ORM migrations. Schema changes are managed through SQL files, not Alembic.

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_character.py

# Run with coverage
pytest --cov=app tests/
```

## Code Structure

```
/
├── app.py                 # Flask application entry point
├── config.py              # Configuration (DB, API keys, env-specific settings)
├── requirements.txt       # Python dependencies
├── ARCHITECTURE.md        # Detailed technical architecture
├── database/              # Database schema and procedures
│   ├── schemas/
│   │   ├── game.sql       # Game state schema and tables
│   │   ├── character.sql  # Character-related schema and tables
│   │   ├── world.sql      # Locations, items schema and tables
│   │   └── memory.sql     # Turn history, summaries schema and tables
│   └── procedures/
│       ├── character_procedures.sql
│       ├── location_procedures.sql
│       ├── turn_procedures.sql
│       ├── wound_procedures.sql
│       └── relationship_procedures.sql
├── models/                # SQLAlchemy models (thin wrappers)
│   ├── character.py
│   ├── location.py
│   ├── turn.py
│   ├── wound.py
│   └── relationship.py
├── services/              # Business logic
│   ├── llm/
│   │   ├── provider.py    # Abstract LLM provider
│   │   ├── claude.py      # Anthropic implementation
│   │   └── openai.py      # OpenAI implementation
│   ├── memory/
│   │   ├── working_memory.py
│   │   ├── vector_store.py
│   │   └── summarizer.py
│   ├── game_engine.py     # Turn-based game loop
│   ├── action_generator.py  # Generate action options via LLM
│   ├── context_assembler.py # Assemble context for prompts
│   ├── injury_system.py   # Wound deterioration, treatment
│   └── relationship_graph.py # NetworkX graph operations
├── routes/                # Flask routes
│   ├── game.py           # Main game interface
│   ├── character.py      # Character management
│   └── admin.py          # Admin tools
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── game.html         # Main game UI
│   └── character_sheet.html
├── static/                # CSS, JS, images
│   ├── css/
│   └── js/
├── scripts/               # Utility scripts
│   ├── init_db.py        # Database initialization (runs schema + procedure files)
│   ├── seed_characters.py # Create initial characters via procedures
│   └── test_llm.py       # Test LLM connections
└── tests/                 # Test suite
```

## Character Profile Structure

When working with character data, remember these key components:

### Always Present
- **Core Identity**: name, backstory, physical_appearance, current_clothing, role_responsibilities
- **Personality**: personality_traits (JSONB), speech_style, education_level, current_emotional_state
- **Motivations**: motivations_short_term, motivations_long_term (both JSONB arrays)
- **Preferences**: food, clothing_style, attraction_types, activities, locations (JSONB)
- **Knowledge**: skills (JSONB), education_level, superstitions, hobbies
- **Social**: social_class, reputation (per faction), relationships (separate table)
- **Secrets**: secrets (JSONB) - never revealed in character's dialogue/actions
- **Physical State**: current_stance, wounds (separate table), fatigue, hunger

### Dynamic State
- **Location**: current_location_id
- **Inventory**: character_inventory table
- **Wounds**: character_wound table with deterioration tracking
- **Relationships**: character_relationship table (trust/fear/respect)

## Injury System Rules

When implementing injury-related features:

1. **No HP/Health Bars**: Wounds are narrative and specific
2. **Body Parts**: head, torso, left_arm, right_arm, left_leg, right_leg
3. **Wound Types**: cut, stab, blunt_trauma, burn, infection
4. **Severity Levels**: minor, moderate, severe, critical, mortal
5. **Deterioration**:
   - Untreated wounds worsen over turns
   - Bleeding causes death if not stopped
   - Infections develop in dirty environments
   - Mortal wounds → death if time passes without expert treatment
6. **Treatment**:
   - Requires medical skill check
   - Herbal remedies less effective than modern (non-existent) medicine
   - Improper treatment can worsen wounds

## LLM Context Assembly

When assembling context for action generation:

```python
# Order matters - this is optimal prompt structure
context = {
    "character_profile": {...},           # Full character data
    "current_location": {...},            # Where they are
    "visible_characters": [...],          # Who they can see
    "working_memory": [...],              # Last 10 turns
    "session_summary": "...",             # Compressed recent history
    "relevant_long_term_memories": [...], # From vector search
    "relationships": {...},               # With visible characters
    "private_thoughts": [...],            # Character's internal state
    "current_wounds": [...],              # Injury status
    "inventory": [...]                    # What they're carrying
}
```

### Context Size Management

**Situational Awareness (New!):**
The system now dynamically includes only contextually relevant character attributes:
- **Always included**: objectives, appearance, clothing, items, stance, state, personality
- **Conditionally included**: food preferences (when eating), hobbies (in leisure contexts), superstitions (supernatural events), attraction types (romance), education (scholarly contexts), social class (political contexts)
- **Token savings**: 30-43% reduction in irrelevant details
- **Adaptive memory windows**: 5 turns (8K models), 8 turns (32K models), 10 turns (128K+ models)
- **Dynamic summary priorities**: Elevated to HIGH for restrictive models

**Model-Aware Context Assembly:**
- System automatically adapts context to model's window size
- Priority-based component inclusion (CRITICAL → HIGH → MEDIUM → LOW → OPTIONAL)
- Intelligent truncation preserves meaning without breaking mid-sentence
- Works with models from 8K to 200K token windows

**Typical Context Sizes:**
- Character identity: 200-500 tokens (CRITICAL - always included, but dynamically filtered)
- Current situation: 300-800 tokens (CRITICAL - always included)
- Working memory (5-10 turns): 1,750-5,000 tokens (HIGH priority, adaptive window)
- Relationships: 500-3,000 tokens (HIGH priority)
- Character state (wounds/inventory): 200-1,000 tokens (HIGH priority)
- Session summaries: 1,000-4,000 tokens (HIGH/MEDIUM priority, elevated for small models)
- Long-term memories: 3,000-8,000 tokens (LOW priority)
- Extended backstory: 1,000-5,000 tokens (OPTIONAL - first to drop)

**Total Context:** 8,000-25,000 tokens (before adaptation)
- Small models (8K): Auto-trimmed to ~4,500-5,500 tokens (5-turn window, relevant attrs only)
- Medium models (32K): Fits most content (~12,000-18,000 tokens, 8-turn window)
- Large models (128K+): All content fits (10-turn window, all attributes)

See `CONTEXT_GUIDE.md` for detailed documentation.

## Turn-Based Game Loop

Each turn follows this sequence:

1. **Determine order**: Randomize all characters (AI + players)
2. **For each character**:
   - Assemble context from 3 memory tiers + relationship graph
   - Generate 4-6 action options via LLM
   - If player: present options in UI, wait for selection
   - If AI: use lightweight model to pick option or use rules-based selection
   - Execute action(s): update DB, relationships, injuries
   - Record in turn_history (see Multi-Action Turns below)
   - Embed significant actions in vector DB
3. **Post-turn updates**:
   - Check wound deterioration (bleeding, infection)
   - Update character states (fatigue, starvation)
   - Check win/lose conditions
4. **Every 10 turns**: Summarize working memory to short-term memory

### Multi-Action Turns (Sequence System)

A character's turn can contain **multiple sequenced actions** that execute in order. This allows complex narrative turns like: *think → speak → act*.

**Key concepts:**

1. **Sequence Number**: Each action gets `sequence_number` (0, 1, 2...) to maintain order
2. **Private vs Public**:
   - `is_private = true`: Only the character knows (thoughts, hidden actions)
   - `is_private = false`: Can be witnessed by others in same location
3. **Witnesses**: Array of character_ids who saw the action (empty for private)

**Example turn:**
```python
# Sequence 0: Private thought
turn_history_create(
    turn_number=15, character_id=A, sequence_number=0,
    action_type='think',
    action_description='I can deceive Character B...',
    is_private=True  # Only Character A knows
)

# Sequence 1: Public speech
turn_history_create(
    turn_number=15, character_id=A, sequence_number=1,
    action_type='speak',
    action_description='Character A says "I\'m glad you are here..."',
    is_private=False,
    witnesses=['B', 'C']  # B and C hear this
)

# Sequence 2: Public action
turn_history_create(
    turn_number=15, character_id=A, sequence_number=2,
    action_type='interact',
    action_description='Character A touches B\'s arm',
    is_private=False,
    witnesses=['B', 'C']
)
```

**What each character sees:**
- **Character A** (actor): All 3 actions (including private thought)
- **Character B** (witness): Sequences 1 & 2 only (public actions)
- **Character C** (witness): Sequences 1 & 2 only (public actions)
- **Character D** (not present): Nothing

**Querying turns:**
```python
# Get what Character B witnessed (their own actions + public actions they saw)
turn_history_get_witnessed(game_id, character_B_id, last_n_turns=10)

# Get full working memory (all actions, all characters)
turn_history_get_working_memory(game_id, last_n_turns=10)
```

See `database/TURN_SEQUENCE.md` for detailed examples and Python code.

**Note on character_thought table:** The separate `memory.character_thought` table is deprecated in favor of using `is_private=true` in `turn_history`. This keeps all actions chronologically ordered in one place. However, the table remains for backward compatibility or alternative use cases.

## Important Design Principles

### What Characters Know
- Characters only perceive other characters in the **same location**
- Characters only know their own **private thoughts**
- Characters remember events they **witnessed** or were **told about**
- Characters' **opinions** of others can change based on interactions

### What Players See
- Current location description
- Visible characters and their stances/appearance
- Their own character's thoughts (private)
- Available action options (generated by LLM)
- Outcomes of their actions
- Turn number and turn order

### LLM Prompting Guidelines
- **System prompt**: Establish dark fantasy gothic tone, no magic, realistic injuries
- **Character voice**: Use speech_style from profile
- **Action realism**: Characters should act according to motivations, fears, relationships
- **Consistency**: Reference relationship graph and memory when generating actions
- **Secrets**: Characters never explicitly reveal secrets unless forced by situation
- **Wound awareness**: Characters react to injuries realistically (pain, fear, impairment)

## Common Pitfalls to Avoid

1. **Don't let characters know things they haven't witnessed**
   - Use `turn_history_get_witnessed()` procedure to check witnessed events before giving character knowledge

2. **Don't ignore wounds**
   - Always use `character_wound_list()` procedure before allowing physical actions
   - Severe wounds should limit actions

3. **Don't forget relationship updates**
   - Every significant social interaction should call `character_relationship_upsert()` to update the relationship graph

4. **Don't access tables directly**
   - Always use stored procedures for all database operations
   - Never write raw SELECT/INSERT/UPDATE/DELETE against tables

5. **Don't exceed token budgets**
   - Monitor context size, trim old working memory if needed

6. **Don't use magic**
   - Herbalism is mundane, not magical (even if some characters think it is)

7. **Don't make injuries trivial**
   - A stab wound should be a major event, not a minor inconvenience

## Environment Variables Required

```
NEON_DATABASE_URL=postgresql://user:pass@host/db
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
FLASK_SECRET_KEY=random-secret-key
FLASK_ENV=development
QDRANT_HOST=https://your-instance.gcp.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_DIMENSION=1536
```

## Cost Optimization Tips

- Use **Claude Haiku** for summarization (10x cheaper than Sonnet)
- Use **GPT-3.5-turbo** for non-critical AI character decisions
- **Cache** action options for repeated similar contexts
- Only embed **significant** events in vector DB, not every turn
- Batch embedding requests when possible
- Use **shorter prompts** for simple actions (movement, inventory)

## Testing Approach

- **Stored procedure tests**: Test procedures directly with SQL (in `tests/sql/`)
  - Use a test database or transaction rollback
  - Verify data integrity, constraints, and business logic
- **Unit tests**: Models (verify they call correct procedures), services (mock LLM calls)
- **Integration tests**: Game loop, database operations via procedures
- **LLM tests**: Use fixtures with pre-generated responses
- **Smoke tests**: Can the game run for 10 turns without errors?

### Testing Stored Procedures
```python
# Test that character_upsert works correctly
def test_character_upsert():
    db.execute("BEGIN")

    result = db.execute(
        "SELECT character_upsert(:id, :name, :backstory, ...)",
        {"id": uuid4(), "name": "Test Character", ...}
    )

    # Verify character was created
    character = db.execute(
        "SELECT * FROM character_get(:id)",
        {"id": result.character_id}
    ).fetchone()

    assert character.name == "Test Character"

    db.execute("ROLLBACK")
```

## Debugging

```python
# Enable SQL logging (see stored procedure calls)
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Log LLM prompts
logger.info(f"Prompt to LLM: {prompt[:500]}...")
logger.info(f"LLM response: {response}")

# Check context size
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
tokens = len(enc.encode(prompt))
logger.info(f"Prompt tokens: {tokens}")
```

### Debugging Stored Procedures
```sql
-- Test procedure directly in psql
SELECT * FROM character_get('550e8400-e29b-41d4-a716-446655440000');

-- Add RAISE NOTICE for debugging inside procedures
CREATE OR REPLACE FUNCTION character_get(p_character_id UUID)
RETURNS TABLE(...) AS $$
BEGIN
    RAISE NOTICE 'Getting character with ID: %', p_character_id;
    -- ... rest of procedure
END;
$$ LANGUAGE plpgsql;

-- View procedure execution plan
EXPLAIN ANALYZE SELECT * FROM character_list_by_location('location-uuid');
```

## Prototype MVP Scope

The initial prototype includes:
- ✅ 2 locations (tavern, street)
- ✅ 3 characters (1 player, 2 AI)
- ✅ Turn-based movement
- ✅ Basic conversation
- ✅ Simple injury system (1-2 wound types)
- ✅ Relationship tracking (trust metric only)
- ✅ Working memory (last 10 turns)

NOT in prototype:
- ❌ Combat resolution (use narrative descriptions)
- ❌ Complex skill checks
- ❌ Full medical system
- ❌ Multiple simultaneous games

## Future Enhancements (Post-MVP)

1. **Vector memory integration**: Connect Qdrant to turn execution (service implemented, see QDRANT_MIGRATION.md)
2. **Combat system**: Dice rolls or deterministic based on skills
3. **Factions**: Groups with collective opinions of characters
4. **Time of day**: Affects character schedules, location availability
5. **Items with properties**: Weapons, herbs, tools with mechanical effects
6. **Skill progression**: Characters can learn and improve
7. **Multiple save games**: Support concurrent playthroughs
8. **Admin dashboard**: Monitor game state, edit characters mid-game
