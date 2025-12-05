# Deydric Must Die - Technical Architecture

## System Overview

A turn-based text adventure game with LLM-generated content, set in a dark fantasy/gothic world. Characters have rich personalities, complex relationships, and realistic injury systems.

## Tech Stack

### Core Application
- **Python 3.11+**: Main language
- **Flask**: Web framework
- **Jinja2**: HTML templating
- **SQLAlchemy**: ORM for database operations

### Data Storage Layers

#### 1. Primary Database: PostgreSQL (Neon)
**Purpose**: Core game state, structured data
**Stores**:
- Character profiles (demographics, traits, skills)
- Current game state (turn number, active characters, locations)
- Location/room data (descriptions, connections, items)
- Turn history (actions taken, outcomes)
- Character inventories
- Wounds/injuries with timestamps
- Relationship graph (as JSONB for prototype, can migrate to dedicated graph DB)

**Why Neon**:
- Generous free tier (512MB storage, 0.5 compute units)
- Serverless with autoscaling
- Low latency
- Built-in connection pooling

#### 2. Vector Database: Chroma (prototype) → Pinecone (production)
**Purpose**: Semantic memory search
**Stores**:
- Embedded character memories
- Embedded conversation history
- Embedded observed events
- Character thought embeddings

**Why Chroma for prototype**:
- Free, runs locally or in-memory
- Simple Python API
- Easy to switch to Pinecone later

**Why Pinecone for production**:
- Free tier: 1 index, 5M vectors (should handle thousands of game turns)
- Fast semantic search
- Managed service

#### 3. Relationship & Context Graph: NetworkX (in-memory/cached)
**Purpose**: Track character relationships and event causality
**Stores**:
- Character-to-character relationships (nodes: characters, edges: relationship properties)
- Event causality chains (what led to what)
- Location connections (navigation graph)

**Why NetworkX**:
- Pure Python, no external database needed
- Can serialize to PostgreSQL JSONB
- Can migrate to Neo4j if graph becomes very large

### LLM Integration

#### Supported Providers
1. **Anthropic Claude** (via anthropic SDK)
   - Claude 3.5 Sonnet: Main character generation ($3/$15 per MTok)
   - Claude 3 Haiku: Quick actions/summaries ($0.25/$1.25 per MTok)

2. **OpenAI** (via openai SDK)
   - GPT-4: Alternative for complex reasoning
   - GPT-3.5-turbo: Budget option

#### Provider Abstraction Layer
```python
class LLMProvider(ABC):
    @abstractmethod
    def generate_action_options(context: dict) -> list[str]

    @abstractmethod
    def generate_response(prompt: str, context: dict) -> str
```

Implementations: `ClaudeProvider`, `OpenAIProvider`

### Embeddings
- **text-embedding-3-small** (OpenAI): $0.02 per 1M tokens, 1536 dimensions
- Alternative: **voyage-2** (Voyage AI): Better quality, similar pricing

## Memory System Architecture

### Three-Tiered Memory + Graph

#### Working Memory (PostgreSQL)
- **Scope**: Current turn + last 5 turns
- **Storage**: Full detail in `turn_history` table
- **Access**: Direct SQL query, O(1) retrieval

#### Short-Term Memory (PostgreSQL + Summarization)
- **Scope**: Last 25-50 turns
- **Storage**: Summarized every 5 turns by Claude Haiku
- **Format**: Compressed narrative summaries in `memory_summaries` table

#### Long-Term Memory (Vector DB)
- **Scope**: All historical significant events
- **Storage**: Embedded event/thought fragments in Chroma/Pinecone
- **Retrieval**: Semantic search based on current context
- **Query**: "Character X is confronting Y about betrayal" → retrieves similar past confrontations

#### Relationship Graph (NetworkX → PostgreSQL JSONB)
- **Nodes**: Characters
- **Edges**: Relationships with properties:
  - `relationship_type`: friend, enemy, family, romantic, professional, stranger
  - `trust`: -100 to +100
  - `fear`: 0 to 100
  - `respect`: 0 to 100
  - `intimacy`: 0 to 100
  - `antagonism`: 0 to 100
  - `history`: list of significant interaction IDs
  - `last_interaction_turn`: integer
  - `sentiment_trend`: improving, stable, deteriorating

### Context Assembly for LLM Prompts

When generating actions for Character X:
```
1. Fetch from PostgreSQL:
   - Character X full profile
   - Current location details
   - Characters in same location (with their visible state)
   - Last 10 turns (working memory)
   - Short-term summary for this session

2. Fetch from Vector DB:
   - Top 5 semantically similar memories to current situation
   - Character X's private thoughts from similar contexts

3. Fetch from Relationship Graph:
   - Relationships with characters in current location
   - Recent relationship changes

4. Assemble into prompt:
   [Character Profile]
   [Current Situation]
   [Visible Characters & Their States]
   [Recent History - 10 turns]
   [Session Summary]
   [Relevant Memories - 5 items]
   [Relationships Context]
   [Private Thoughts]

   Generate 4-6 action options...
```

## Injury & Health System

### Wound Tracking (PostgreSQL)
Each wound is a record in `character_wounds` table:
```
- wound_id
- character_id
- body_part: head, torso, left_arm, right_arm, left_leg, right_leg
- wound_type: cut, stab, blunt_trauma, burn, infection
- severity: minor, moderate, severe, critical, mortal
- bleeding: boolean
- infected: boolean
- turn_acquired
- turn_last_updated
- description: "Deep stab wound to the abdomen"
- treatment_history: JSONB array of treatments applied
```

### Wound Deterioration
- Each turn, untreated wounds may:
  - Start bleeding (chance based on severity)
  - Become infected (especially cuts, based on environment)
  - Worsen in severity
  - Cause death if mortal + time passed

### Treatment System
- Medical skill check (character attribute)
- Herbal remedies effectiveness varies
- Proper treatment stabilizes, improper treatment worsens
- No healing bars - narrative descriptions only

## Turn-Based Game Loop

### Turn Structure
```
1. Determine turn order (randomized each round)
2. For each character in order:
   a. If AI character:
      - Assemble context (working + short-term + vector search)
      - Query LLM for action options (4-6 options)
      - Use simpler decision model to pick action or present to player
   b. If player character:
      - Assemble context
      - Query LLM for action options
      - Present to player via web UI
      - Wait for player selection
   c. Execute chosen action:
      - Update game state (movement, injuries, inventory)
      - Record in turn_history
      - Update relationship graph if social interaction
      - Embed action in vector DB if significant
      - Generate narrative outcome
   d. Check for wound deterioration
   e. Update character states (fatigue, bleeding out, etc.)
3. Check win/lose conditions
4. Advance turn counter
5. Summarize if turn % 10 == 0
```

### Movement System
- Locations stored in `locations` table with JSONB connections
- Movement action: "Go to [location]"
- Updates `character_current_location`
- Characters only perceive others in same location
- Can track/follow other characters (skill-based)

## Prototype Scope (MVP)

### Characters
- 1 player character
- 2 AI characters
- Minimal profiles (can expand later)

### Locations
- 2 rooms with simple connection
- Example: "Court Yard" ↔ "Guest Bedchamber"

### Features
- Turn-based movement
- Basic conversation
- Simple injury system (1 wound type)
- Relationship tracking (trust only)
- Working memory only (no vector DB initially)

### NOT in Prototype
- Combat resolution mechanics (can use narrative descriptions)
- Complex skill checks
- Full medical system
- Long-term memory / vector search

## Database Schema (Core Tables)

### characters
```sql
id, fullname, shortname, backstory, personality_traits (JSONB),
motivations_short_term (JSONB), motivations_long_term (JSONB),
preferences (JSONB), physical_appearance (TEXT),
current_clothing (TEXT), current_stance (VARCHAR),
role_responsibilities (TEXT), speech_style (TEXT),
education_level (VARCHAR), superstitions (TEXT),
hobbies (JSONB), skills (JSONB), secrets (JSONB),
current_emotional_state (VARCHAR), social_class (VARCHAR),
current_location_id (FK), is_player (BOOLEAN), is_alive (BOOLEAN),
created_at, updated_at
```

### character_relationships
```sql
id, character_id (FK), target_character_id (FK),
relationship_type (VARCHAR), trust (INT), fear (INT),
intimacy (INT), antagonism (INT),
respect (INT), last_interaction_turn (INT),
sentiment_trend (VARCHAR), history (JSONB),
created_at, updated_at
```

### locations
```sql
id, name, description (TEXT), connections (JSONB),
environment_type (VARCHAR), light_level (VARCHAR),
secrets (JSONB), items_present (JSONB), created_at
```

### turn_history
```sql
id, turn_number (INT), character_id (FK),
action_type (VARCHAR), action_description (TEXT),
action_outcome (TEXT), location_id (FK),
witnesses (JSONB array of character_ids),
timestamp, embedding_id (VARCHAR, reference to vector DB)
```

### character_inventory
```sql
id, character_id (FK), item_name (VARCHAR),
item_description (TEXT), quantity (INT), is_hidden (BOOLEAN),
item_properties (JSONB)
```

### character_wounds
```sql
id, character_id (FK), body_part (VARCHAR),
wound_type (VARCHAR), severity (VARCHAR),
bleeding (BOOLEAN), infected (BOOLEAN),
description (TEXT), turn_acquired (INT),
turn_last_updated (INT), treatment_history (JSONB)
```

### memory_summaries
```sql
id, character_id (FK), turn_range_start (INT),
turn_range_end (INT), summary_text (TEXT),
created_at
```

### game_state
```sql
id, current_turn (INT), turn_order (JSONB),
active_game (BOOLEAN), created_at, updated_at
```

## Cost Estimates (Development Phase)

### LLM Usage (per 100 turns, 3 characters)
- Claude Sonnet for actions: ~600 requests × 2K tokens avg = 1.2M tokens
  - Input: ~$3.60, Output: ~$18 = **~$22 per 100 turns**
- Embeddings: ~300 events × 500 tokens = 150K tokens
  - **~$0.003**

### Database
- Neon PostgreSQL: **Free tier sufficient** for development
- Chroma: **Free (local)**
- Total: **~$22-25 per 100 turns**

### Production Optimization
- Use GPT-3.5-turbo for non-critical actions: **~$0.50 per 100 turns**
- Use Claude Haiku for summaries: **~$1 per 100 turns**
- Cache action options: **50% reduction**
- Estimated: **$5-10 per 100 turns** with optimization

## Development Phases

### Phase 1: Core Infrastructure (Week 1-2)
- Flask app skeleton
- PostgreSQL schema on Neon
- Basic character & location models
- Simple web UI (single page)

### Phase 2: Turn System (Week 2-3)
- Turn-based game loop
- Action execution
- Movement between rooms
- Turn history logging

### Phase 3: LLM Integration (Week 3-4)
- Anthropic/OpenAI provider classes
- Context assembly
- Action generation
- Response formatting

### Phase 4: Memory & Relationships (Week 4-5)
- Relationship graph
- Working memory queries
- Short-term summarization

### Phase 5: Injury System (Week 5-6)
- Wound tracking
- Deterioration mechanics
- Treatment system

### Phase 6: Enhanced Memory (Future)
- Vector DB integration (Chroma)
- Semantic memory search
- Long-term memory consolidation

## Recommended Low-Cost Services

1. **Neon** (PostgreSQL): Free tier, upgrade at $19/mo
2. **Chroma** (Vector DB): Free local, or host on Railway ($5/mo)
3. **Anthropic API**: Pay-as-you-go, $3/$15 per MTok
4. **OpenAI API**: Pay-as-you-go, similar pricing
5. **Railway** or **Render** (hosting): Free tier for Flask app
6. **Cloudflare Pages** (optional): Free static asset hosting

**Total Development Cost**: ~$0-5/month + LLM usage (~$20-30/month testing)

## Alternative Considerations

### If Budget is Very Tight
- Use **Ollama** with Llama 3 8B locally (free but needs good GPU)
- Use **LM Studio** for local models
- Use **SQLite** instead of Neon (limits collaboration)
- Skip vector DB initially, use full-text search in PostgreSQL

### If Scaling is Priority
- Use **Supabase** instead of Neon (more features, similar pricing)
- Use **Qdrant** or **Weaviate Cloud** instead of Pinecone (open source options)
- Use **Neo4j Aura Free** for relationship graphs
- Add **Redis Cloud** (free 30MB) for caching

## Next Steps

1. Set up development environment (Python venv, Flask)
2. Create Neon database (free account)
3. Get API keys (Anthropic, OpenAI)
4. Build minimal prototype (2 rooms, 3 characters, basic turns)
5. Test gameplay loop
6. Iterate on character depth
7. Add memory systems progressively
