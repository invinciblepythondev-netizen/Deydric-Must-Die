# Game Loop Analysis - Gaps and Missing Components

## Executive Summary

The game has excellent **foundation systems** (time tracking, mood tracking, action generation, multi-action sequences) but is **missing critical integration layers** between database and gameplay. Most stored procedures exist, but Python models/services to use them are incomplete.

**Prototype Status**: ~40% complete
**Critical Path**: Models → Action Executor → Game Engine → Routes/UI

---

## Current Game Loop (Ideal Flow)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GAME INITIALIZATION                                          │
│    - Create game_state                                          │
│    - Initialize locations                                       │
│    - Create/load characters                                     │
│    - Set starting positions                                     │
│    - Initialize mood (neutral)                                  │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. TURN START                                                   │
│    - Get current turn number                                    │
│    - Get turn order (randomized or stat-based)                  │
│    - Get time of day                                            │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. FOR EACH CHARACTER IN TURN ORDER                             │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3a. GATHER CONTEXT                                      │ │
│    │     - Character profile                                 │ │
│    │     - Current location                                  │ │
│    │     - Visible characters                                │ │
│    │     - Relationships with visible characters            │ │
│    │     - Working memory (witnessed actions)               │ │
│    │     - Character state (wounds, status effects)         │ │
│    │     - Inventory                                         │ │
│    │     - Mood at location                                  │ │
│    │     - Time of day                                       │ │
│    └─────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3b. GENERATE ACTION OPTIONS                             │ │
│    │     - Build context for LLM                             │ │
│    │     - Call action generator                             │ │
│    │     - Get 4-6 diverse multi-action sequences          │ │
│    │     - Ensure de-escalation option present              │ │
│    └─────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3c. SELECT ACTION                                       │ │
│    │     - IF AI: Random weighted selection                  │ │
│    │     - IF Player: Present options, wait for choice      │ │
│    └─────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3d. VALIDATE ACTION                                     │ │
│    │     - Check if character can perform action             │ │
│    │     - Skill checks if needed                            │ │
│    │     - Check prerequisites (items, location, etc.)       │ │
│    └─────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3e. EXECUTE ACTION SEQUENCE                             │ │
│    │     FOR each action in sequence:                        │ │
│    │       - Determine witnesses                              │ │
│    │       - Apply action effects                            │ │
│    │       - Record in turn_history                          │ │
│    │       - Generate outcome description                    │ │
│    └─────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ 3f. UPDATE WORLD STATE                                  │ │
│    │     - Update mood based on action impact                │ │
│    │     - Update relationships if social action             │ │
│    │     - Apply wounds if combat                            │ │
│    │     - Move character if location change                 │ │
│    │     - Transfer items if trading                         │ │
│    └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. TURN END                                                     │
│    - Advance turn number                                        │
│    - Advance time (6 minutes default)                           │
│    - Expire old status effects                                  │
│    - Check wound deterioration                                  │
│    - Check win/lose conditions                                  │
│    - Summarize memory if needed (every 10 turns)                │
└─────────────────────────────────────────────────────────────────┘
                             ↓
                   Loop back to step 2
```

---

## ✅ COMPLETE Components

### Database Layer
- ✅ All schemas (game, character, world, memory)
- ✅ Time tracking (game_state with day/time)
- ✅ Mood tracking (scene_mood table)
- ✅ Turn sequence support (sequence_number)
- ✅ Character status effects
- ✅ All stored procedures:
  - character_procedures.sql
  - character_status_procedures.sql
  - game_state_procedures.sql
  - location_procedures.sql
  - mood_procedures.sql
  - relationship_procedures.sql
  - turn_procedures.sql
  - wound_procedures.sql

### Models (Thin Wrappers)
- ✅ ActionSequence, ActionOption, GeneratedActionOptions
- ✅ CharacterStatus (status effects)
- ✅ GameTime, GameState (time tracking)
- ✅ SceneMood (mood tracking)

### Services
- ✅ ActionGenerator (LLM-powered action generation)
- ✅ ActionSelector (AI random / player choice)
- ✅ ContextManager (adaptive context assembly)
- ✅ LLM providers (Claude, OpenAI, AIML, resilient generator)

### Documentation
- ✅ TIME_TRACKING_GUIDE.md
- ✅ ACTION_GENERATION_GUIDE.md
- ✅ CONTEXT_GUIDE.md
- ✅ PROVIDER_FALLBACK_GUIDE.md
- ✅ ARCHITECTURE.md

---

## ❌ MISSING Components (Critical Path)

### 1. Models (Python Wrappers) - **HIGH PRIORITY**

**Missing Models:**

#### Character Model
```python
# models/character.py - MISSING
class Character:
    @staticmethod
    def get(db, character_id) -> Dict

    @staticmethod
    def create(...) -> UUID

    @staticmethod
    def list_by_location(db, location_id) -> List[Dict]

    @staticmethod
    def update_location(db, character_id, new_location_id)

    @staticmethod
    def get_inventory(db, character_id) -> List[Dict]

    @staticmethod
    def get_wounds(db, character_id) -> List[Dict]
```

**Database procedures exist**, just need thin wrapper.

#### Location Model
```python
# models/location.py - MISSING
class Location:
    @staticmethod
    def get(db, location_id) -> Dict

    @staticmethod
    def list_all(db, game_state_id) -> List[Dict]

    @staticmethod
    def get_connections(db, location_id) -> List[int]

    @staticmethod
    def get_characters_at(db, location_id) -> List[Dict]
```

**Database procedures exist**, just need thin wrapper.

#### Turn Model
```python
# models/turn.py - MISSING
class Turn:
    @staticmethod
    def create_action(db, ...) -> UUID  # Wraps turn_history_create

    @staticmethod
    def get_working_memory(db, game_state_id, n_turns=10) -> List[Dict]

    @staticmethod
    def get_witnessed(db, character_id, n_turns=10) -> List[Dict]
```

**Database procedures exist**, just need thin wrapper.

#### Wound Model
```python
# models/wound.py - MISSING
class Wound:
    @staticmethod
    def create(db, character_id, ...) -> UUID

    @staticmethod
    def list_by_character(db, character_id) -> List[Dict]

    @staticmethod
    def check_deterioration(db, wound_id, current_turn) -> Dict
```

**Database procedures exist**, just need thin wrapper.

#### Relationship Model
```python
# models/relationship.py - MISSING
class Relationship:
    @staticmethod
    def get(db, source_id, target_id) -> Dict

    @staticmethod
    def update(db, source_id, target_id, trust_delta, ...) -> Dict

    @staticmethod
    def get_all_for_character(db, character_id) -> List[Dict]
```

**Database procedures exist**, just need thin wrapper.

---

### 2. Services (Business Logic) - **HIGH PRIORITY**

#### Action Executor - **CRITICAL**
```python
# services/action_executor.py - MISSING
class ActionExecutor:
    """
    Executes a selected ActionSequence, applying effects and recording outcomes.
    """

    def execute_sequence(
        self,
        db,
        character_id: UUID,
        selected_option: ActionOption,
        game_state_id: UUID,
        current_turn: int
    ) -> ExecutionResult:
        """
        Execute all actions in sequence:
        1. For each action:
           - Determine witnesses
           - Apply action effects (combat, movement, items)
           - Record in turn_history with sequence_number
           - Generate outcome description
        2. Update mood
        3. Update relationships
        4. Return result summary
        """
```

**This is the biggest gap** - bridges action generation to world state changes.

#### Turn Order Manager - **CRITICAL**
```python
# services/turn_order.py - MISSING
class TurnOrderManager:
    """
    Manages turn order (randomized or stat-based).
    """

    @staticmethod
    def determine_turn_order(
        db,
        game_state_id: UUID,
        characters: List[UUID]
    ) -> List[UUID]:
        """
        Randomize character order for this turn.
        Later: Can use dexterity/initiative stats.
        """

    @staticmethod
    def get_next_character(db, game_state_id) -> Optional[UUID]:
        """Get next character in turn order."""
```

#### Skill Checker - **MEDIUM PRIORITY**
```python
# services/skill_checker.py - MISSING
class SkillChecker:
    """
    Validates if character can perform action and resolves skill checks.
    """

    @staticmethod
    def can_perform_action(
        character: Dict,
        action: SingleAction,
        context: Dict
    ) -> Tuple[bool, str]:
        """
        Check if action is valid.
        Returns: (can_perform, reason_if_not)
        """

    @staticmethod
    def resolve_skill_check(
        character: Dict,
        skill_name: str,
        difficulty: int
    ) -> Tuple[bool, int]:
        """
        Roll skill check.
        Returns: (success, roll_value)
        """
```

#### Combat Resolver - **MEDIUM PRIORITY**
```python
# services/combat_resolver.py - MISSING
class CombatResolver:
    """
    Resolves attack actions, determines wounds.
    """

    @staticmethod
    def resolve_attack(
        attacker: Dict,
        defender: Dict,
        weapon: Optional[Dict],
        context: Dict
    ) -> AttackResult:
        """
        Determine if attack hits, apply wounds.
        Returns wound details or miss.
        """
```

#### Consequence Handler - **MEDIUM PRIORITY**
```python
# services/consequence_handler.py - MISSING
class ConsequenceHandler:
    """
    Handles side effects of actions (discovery, reactions, cascading events).
    """

    @staticmethod
    def check_for_discovery(
        action: SingleAction,
        witnesses: List[UUID],
        character: Dict
    ) -> Optional[DiscoveryEvent]:
        """
        Did anyone notice a hidden action (stealing, hiding)?
        """

    @staticmethod
    def generate_reactions(
        action: SingleAction,
        witnesses: List[UUID]
    ) -> List[ReactionEvent]:
        """
        Do witnesses react immediately (gasp, intervene)?
        """
```

#### Witness Tracker - **LOW PRIORITY** (for prototype)
```python
# services/witness_tracker.py - MISSING
class WitnessTracker:
    """
    Determines who witnesses each action.
    """

    @staticmethod
    def get_witnesses_for_action(
        action: SingleAction,
        location: Dict,
        all_characters: List[Dict]
    ) -> List[UUID]:
        """
        Who is present and can see/hear this action?
        - Same location
        - Not hidden/stealth
        - Conscious
        """
```

#### Game Engine (Orchestrator) - **CRITICAL**
```python
# services/game_engine.py - MISSING
class GameEngine:
    """
    Main orchestrator - runs the game loop.
    """

    def __init__(self, db_session, llm_provider):
        self.db = db_session
        self.action_generator = ActionGenerator(llm_provider)
        self.action_executor = ActionExecutor()
        self.turn_order_mgr = TurnOrderManager()
        # ... other services

    def start_new_game(self, config: Dict) -> UUID:
        """Initialize new game state."""

    def process_turn(self, game_state_id: UUID) -> TurnResult:
        """Execute one complete turn for all characters."""

    def process_character_turn(
        self,
        game_state_id: UUID,
        character_id: UUID
    ) -> CharacterTurnResult:
        """Process one character's turn."""

    def check_end_conditions(self, game_state_id: UUID) -> Optional[str]:
        """Check if game is over (win/lose)."""
```

---

### 3. Flask Application - **HIGH PRIORITY**

#### App Entry Point
```python
# app.py - MISSING
from flask import Flask, render_template, request, redirect
from routes import game_routes

app = Flask(__name__)
app.config.from_object('config.Config')

# Register routes
app.register_blueprint(game_routes.bp)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
```

#### Routes
```python
# routes/game.py - MISSING
from flask import Blueprint, render_template, request, jsonify, session

bp = Blueprint('game', __name__, url_prefix='/game')

@bp.route('/new', methods=['GET', 'POST'])
def new_game():
    """Create new game."""

@bp.route('/<game_id>', methods=['GET'])
def game_view(game_id):
    """Main game interface."""

@bp.route('/<game_id>/action', methods=['POST'])
def submit_action(game_id):
    """Player submits action choice."""

@bp.route('/<game_id>/state', methods=['GET'])
def game_state(game_id):
    """Get current game state (for AJAX updates)."""
```

---

### 4. Templates (Jinja2) - **HIGH PRIORITY**

```
templates/
├── base.html          - MISSING (base layout)
├── index.html         - MISSING (landing page)
├── game.html          - MISSING (main game UI)
├── character_sheet.html - MISSING (character details)
└── components/
    ├── action_options.html - MISSING (action selection UI)
    ├── turn_history.html   - MISSING (history display)
    └── character_list.html - MISSING (visible characters)
```

---

### 5. Supporting Systems - **LOWER PRIORITY**

#### Memory Summarizer
```python
# services/memory_summarizer.py - MISSING
class MemorySummarizer:
    """Summarizes working memory into short-term summaries."""

    def summarize_turns(
        self,
        db,
        game_state_id: UUID,
        start_turn: int,
        end_turn: int
    ) -> str:
        """Use Haiku to summarize turn range."""
```

#### Vector Memory Manager
```python
# services/vector_memory.py - MISSING
class VectorMemoryManager:
    """Manages long-term memory in vector database."""

    def embed_significant_action(
        self,
        turn_id: UUID,
        description: str,
        significance: float
    ):
        """Embed action if significance > threshold."""

    def search_relevant_memories(
        self,
        query: str,
        character_id: UUID,
        top_k: int = 5
    ) -> List[Dict]:
        """Semantic search for relevant past events."""
```

#### Relationship Graph Manager
```python
# services/relationship_graph.py - MISSING
import networkx as nx

class RelationshipGraphManager:
    """Manages NetworkX graph of character relationships."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_character(self, character_id: UUID):
        """Add node to graph."""

    def update_relationship(
        self,
        source_id: UUID,
        target_id: UUID,
        trust_delta: int,
        fear_delta: int,
        ...
    ):
        """Update edge properties."""

    def get_relationship_summary(
        self,
        source_id: UUID,
        target_id: UUID
    ) -> str:
        """Get formatted relationship description."""

    def serialize_to_json(self) -> Dict:
        """Serialize graph for PostgreSQL storage."""

    def load_from_json(self, data: Dict):
        """Restore graph from PostgreSQL."""
```

---

## Priority Matrix for Prototype

### Phase 1: Core Models (2-3 hours)
**Must have for prototype:**
1. ✅ ActionSequence, ActionOption (done)
2. ✅ SceneMood (done)
3. ✅ GameTime (done)
4. ❌ Character model
5. ❌ Location model
6. ❌ Turn model

### Phase 2: Action Execution (3-4 hours)
**Critical for functional gameplay:**
1. ❌ ActionExecutor (apply effects, record turn_history)
2. ❌ TurnOrderManager (randomize turns)
3. ❌ WitnessTracker (determine who sees actions)
4. ❌ Basic ConsequenceHandler (just update mood/relationships)

### Phase 3: Game Engine (2-3 hours)
**Orchestrates everything:**
1. ❌ GameEngine class
   - start_new_game()
   - process_turn()
   - process_character_turn()

### Phase 4: Flask App (3-4 hours)
**User-facing:**
1. ❌ app.py
2. ❌ routes/game.py
3. ❌ templates/base.html, game.html, action_options.html

### Phase 5: Data Seeding (1 hour)
**Test content:**
1. ❌ scripts/seed_data.py
   - Create 2 locations
   - Create 3 characters (1 player, 2 AI)
   - Set starting positions

---

## NOT Needed for Prototype

These can wait for post-MVP:

- ❌ Combat resolver (narrative only for prototype)
- ❌ Skill checks (assume all actions succeed for prototype)
- ❌ Vector memory (just use working memory + short summaries)
- ❌ Relationship graph (use simple relationship table queries)
- ❌ Save/load system (single game only)
- ❌ Character creation (use pre-seeded characters)
- ❌ Item system complexity (basic inventory only)
- ❌ Wound deterioration (just track wounds, no decay)
- ❌ Status effect expiry (manual for prototype)

---

## Critical Dependencies

```
Models → ActionExecutor → GameEngine → Routes → UI
   ↓
Turn procedures (already exist ✅)
```

**Blocker Chain:**
- Can't build ActionExecutor without Character/Location/Turn models
- Can't build GameEngine without ActionExecutor
- Can't build Routes without GameEngine
- Can't build UI without Routes

**Start Here:**
1. Build Character, Location, Turn models (wrappers only!)
2. Build ActionExecutor
3. Build TurnOrderManager + WitnessTracker
4. Build GameEngine
5. Build Flask app + routes
6. Build templates

---

## Estimated Timeline for Prototype MVP

| Phase | Component | Hours | Cumulative |
|-------|-----------|-------|------------|
| 1 | Character, Location, Turn models | 2-3 | 3h |
| 2 | Wound, Relationship models | 1-2 | 5h |
| 3 | ActionExecutor | 3-4 | 9h |
| 4 | TurnOrderManager, WitnessTracker | 2 | 11h |
| 5 | GameEngine | 2-3 | 14h |
| 6 | Flask app.py + config | 1 | 15h |
| 7 | Routes (game.py) | 2-3 | 18h |
| 8 | Templates (base, game, components) | 3-4 | 22h |
| 9 | Seed data script | 1 | 23h |
| 10 | Testing + bug fixes | 3-5 | 28h |

**Total: 23-28 hours** for functional prototype.

---

## Success Criteria (From PROTOTYPE_NEXT_STEPS.md)

✅ **Ready when:**
- Can start a new game with 3 characters
- Player sees 4-6 action options generated by LLM
- Player can select and execute action
- AI characters take automatic turns
- Turn history displays last 10 actions
- Characters can move between 2 locations
- Basic conversations work (speak action)
- Wounds can be inflicted and tracked
- Trust scores update after interactions
- Game runs for 10+ turns without errors

---

## Conclusion

**What's Working:**
- Excellent foundation (database, time, mood, action generation)
- Sophisticated multi-action sequences
- Context-aware LLM prompts

**What's Missing:**
- Integration layer (models, executors, engine)
- Flask application (routes, templates)
- Data seeding

**Next Step:**
Start with Phase 1 - build the thin model wrappers for existing stored procedures. Everything else cascades from there.
