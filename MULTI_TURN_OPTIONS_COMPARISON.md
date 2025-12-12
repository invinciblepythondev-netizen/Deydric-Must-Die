# Multi-Turn Action Tracking: Approach Comparison

## Overview

This document compares 5 different approaches for handling multi-turn actions in the game, ranging from explicit tracking to LLM-driven implicit continuation.

---

## Approach 1: Explicit Intent System (Already Designed)

### Description
Dedicated database table tracks character intents with progress, stages, and targets. Draft generation is explicitly biased toward continuing active intents.

### How It Works
```
Turn 1: Character A → "Flirt with B"
   → Creates database record: intent_type='seduction', progress=20%

Turn 2: Draft generation queries database
   → Finds active intent
   → 60% of drafts continue seduction (varied)
   → 20% escalate, 20% divert

Turn 3: Action taken updates progress
   → Progress now 40%, stage changes
```

### Implementation
- ✅ Already designed (database schema, procedures, Python model)
- New table: `character_intent`
- Stored procedures for CRUD operations
- Action chain templates (seduction, intimidation, etc.)
- Progress detection from keywords

### Pros
✅ **Explicit control** - System knows exactly what character is pursuing
✅ **Trackable progress** - Can show UI indicators, analytics
✅ **Predictable** - Consistent continuation behavior
✅ **Interruptible** - Can detect when intent is abandoned/achieved
✅ **Variety** - Still generates diverse approaches to same goal

### Cons
❌ **More complex** - New table, procedures, integration points
❌ **Rigid templates** - Limited to predefined intent types
❌ **Manual classification** - Need to detect intent from actions
❌ **Storage overhead** - Database records for each intent

### Complexity: **High**
- Database schema changes
- Stored procedures
- Integration with ActionGenerator
- Progress tracking logic

### Best For
- **Structured, trackable progression** in important interactions
- **Games where player needs to see progress** (relationship meters, persuasion bars)
- **Complex multi-stage sequences** (seduction, investigation, combat combos)

---

## Approach 2: Momentum Vector System

### Description
Lightweight mathematical approach. Each character has a "momentum vector" that tracks recent action themes. Similar actions get boosted in draft generation.

### How It Works
```
Turn 1: Character A → "Compliment B"
   → Momentum vector: {romantic: 0.3, social: 0.2}

Turn 2: Draft generation
   → Romantic actions get +3 escalation bonus
   → Social actions get +2 escalation bonus
   → Drafts naturally cluster around recent themes

Turn 3: Action → "Touch B's hand"
   → Momentum: {romantic: 0.6, social: 0.1, physical: 0.3}
   → Momentum decay: old values decrease over time
```

### Implementation
```python
# In-memory or simple JSONB column
character_momentum = {
    'romantic': 0.6,
    'hostile': 0.1,
    'investigative': 0.2,
    'physical': 0.3
}

# Decay each turn
for key in momentum:
    momentum[key] *= 0.8  # 20% decay per turn

# Boost draft scores based on momentum
if momentum.get('romantic', 0) > 0.3:
    romantic_drafts.escalation_score += 3
```

### Pros
✅ **Simple** - Just a JSONB column or in-memory dict
✅ **Flexible** - Handles any action type, not just templates
✅ **Emergent behavior** - Actions naturally cluster
✅ **Self-cleaning** - Momentum decays automatically
✅ **No manual classification** - Keywords auto-categorize

### Cons
❌ **Less explicit** - Can't show "progress bar" for seduction
❌ **Less predictable** - Momentum might shift unexpectedly
❌ **No stages** - Can't track "flirting → touching → intimate"
❌ **Harder to debug** - Why did character suddenly change focus?

### Complexity: **Low**
- Single JSONB column on character table
- Momentum calculation logic
- Draft score boosting

### Best For
- **Organic, emergent behavior** without rigid structure
- **Variety over predictability** in character actions
- **Minimal database changes** and implementation time

---

## Approach 3: LLM-Driven Narrative Memory

### Description
No explicit tracking. The LLM sees recent action history in context and naturally continues themes. Draft generation prompt emphasizes "continue what you started."

### How It Works
```
Turn 1: Character A → "Smile at B and compliment them"
   → Stored in turn_history

Turn 2: Draft generation prompt includes:
   "Recent actions: Turn 1: A smiled at B and complimented them.
    Your drafts should include options to CONTINUE this interaction
    as well as options to CHANGE direction."

Turn 3: LLM generates drafts naturally continuing the theme
```

### Implementation
```python
# In draft generation prompt:
if len(working_memory) > 0:
    recent_actions = working_memory[-3:]  # Last 3 actions

    prompt += f"""
    RECENT ACTION CONTEXT:
    This character recently:
    {format_recent_actions(recent_actions)}

    Generate drafts that include:
    - 12 options that NATURALLY CONTINUE these recent actions
    - 4 options that ESCALATE or intensify
    - 4 options that REDIRECT or change approach
    """
```

### Pros
✅ **Zero database changes** - Uses existing turn_history
✅ **Maximum flexibility** - LLM handles any action type
✅ **Natural language** - No need for keywords or templates
✅ **Variety** - LLM generates creative continuations
✅ **Easy implementation** - Just prompt engineering

### Cons
❌ **Unpredictable** - LLM might not continue as expected
❌ **No progress tracking** - Can't show "50% through seduction"
❌ **Context dependent** - Needs good working memory
❌ **Token heavy** - More context = more tokens
❌ **No explicit control** - Can't force continuation

### Complexity: **Very Low**
- Modify draft generation prompt
- No database changes
- No new models

### Best For
- **Quick implementation** with minimal changes
- **Trusting the LLM** to maintain narrative continuity
- **Games with good working memory** (8+ turns visible)

---

## Approach 4: Action Tags & Continuation Flags

### Description
Each action gets tagged with themes (romantic, hostile, investigative). A simple "continue_last_action" flag biases draft generation.

### How It Works
```
Turn 1: Character A → "Flirt with B"
   → turn_history record: tags=['romantic', 'social']
   → character.continue_last_action = TRUE

Turn 2: Draft generation
   → Sees continue_last_action flag
   → Queries last action's tags: ['romantic', 'social']
   → Generates 60% drafts with same tags

Turn 3: Character picks option
   → If tags match → keep continue_last_action=TRUE
   → If tags differ → set continue_last_action=FALSE
```

### Implementation
```sql
-- Add to turn_history table
ALTER TABLE memory.turn_history
ADD COLUMN action_tags TEXT[];

-- Add to character table
ALTER TABLE character.character
ADD COLUMN continue_last_action BOOLEAN DEFAULT FALSE;
ADD COLUMN last_action_tags TEXT[];

-- In draft generation:
if character.continue_last_action:
    # Boost drafts with matching tags
    for draft in drafts:
        if any(tag in draft.tags for tag in character.last_action_tags):
            draft.escalation_score += 3
```

### Pros
✅ **Simple** - Just columns and flags
✅ **Flexible tags** - Any action type works
✅ **Clear signal** - Flag explicitly says "keep going"
✅ **Trackable** - Can see what themes are active
✅ **Lightweight** - Minimal storage

### Cons
❌ **Binary** - Either continuing or not, no partial progress
❌ **No stages** - Can't track progression through phases
❌ **Manual tagging** - Need to classify action types
❌ **One action at a time** - Can't track multiple intents

### Complexity: **Low-Medium**
- Two new columns
- Tagging logic
- Draft boosting based on tags

### Best For
- **Simple continuation** without complex progression
- **Multiple simultaneous themes** (romantic + investigative + hostile)
- **Balance between explicit and implicit** tracking

---

## Approach 5: Goal Stack System

### Description
Characters maintain a stack of goals (short-term, medium-term, long-term). Top goal influences action generation. Goals can be pushed/popped like a stack.

### How It Works
```
Character A's goal stack:
  [Top]    "Kiss Character B" (short-term, turns: 1-3)
  [Middle] "Seduce Character B" (medium-term, turns: 1-10)
  [Bottom] "Gain B's trust" (long-term, turns: 1-20)

Turn 1: Top goal = "Kiss B"
   → Drafts generated toward kissing
   → Action: "Move closer to B"

Turn 2: Still "Kiss B"
   → Action: "Caress B's face"

Turn 3: Goal achieved!
   → Pop "Kiss B" from stack
   → New top goal: "Seduce B"
   → Continue with next goal
```

### Implementation
```sql
CREATE TABLE character.character_goal (
    goal_id UUID PRIMARY KEY,
    character_id UUID REFERENCES character.character(character_id),
    game_state_id UUID,
    goal_description TEXT,
    goal_priority INTEGER, -- 1 = immediate, 2 = short-term, 3 = long-term
    is_active BOOLEAN DEFAULT TRUE,
    created_turn INTEGER,
    completion_turn INTEGER
);

-- Goals are ordered by priority
-- Draft generation uses top goal (lowest priority number)
```

### Pros
✅ **Hierarchical** - Short/medium/long term goals
✅ **Natural completion** - Pop goal when achieved
✅ **Flexible** - Any goal type works
✅ **Character depth** - Shows layered motivations
✅ **Interruption handling** - Push new urgent goal on top

### Cons
❌ **Complex** - Stack management logic
❌ **No progress tracking** - Binary achieved/not achieved
❌ **Ambiguous completion** - When is goal "done"?
❌ **Overlap issues** - Multiple goals might conflict

### Complexity: **Medium**
- New goal table
- Stack management logic
- Goal completion detection

### Best For
- **Strategic character behavior** with layered motivations
- **Story-driven games** where character goals matter
- **AI characters with plans** (not just reactive)

---

## Comparison Matrix

| Feature | Explicit Intent | Momentum Vector | LLM Memory | Action Tags | Goal Stack |
|---------|----------------|-----------------|------------|-------------|------------|
| **Implementation Complexity** | High | Low | Very Low | Low-Medium | Medium |
| **Database Changes** | New table + procedures | Single column | None | 2 columns | New table |
| **Progress Tracking** | ✅ Explicit % | ❌ Implicit | ❌ None | ❌ Binary flag | ❌ Binary |
| **Variety in Execution** | ✅ High | ✅ High | ✅ Highest | ✅ Medium | ✅ Medium |
| **Predictability** | ✅ High | ⚠️ Medium | ❌ Low | ✅ High | ✅ High |
| **Flexibility** | ⚠️ Template-based | ✅ Any action | ✅ Any action | ✅ Any action | ✅ Any goal |
| **UI Indicators** | ✅ Easy | ❌ Hard | ❌ None | ⚠️ Possible | ✅ Easy |
| **Multi-Intent Support** | ⚠️ One per type | ✅ Multiple vectors | ✅ Context-based | ⚠️ Multiple tags | ✅ Stack order |
| **Interruption Handling** | ✅ Explicit abandon | ✅ Auto-decay | ✅ Context-based | ⚠️ Flag toggle | ✅ Push/pop |
| **Token Usage** | ⚠️ Medium | Low | High (context) | Low | Low |

---

## Hybrid Approaches

### Hybrid 1: Momentum + LLM
- Use momentum vectors for math (boosting scores)
- Use LLM memory for variety (natural continuations)
- **Best of both:** Simple tracking + creative generation

### Hybrid 2: Intent + Tags
- Use intents for major multi-turn sequences (seduction, investigation)
- Use tags for minor themes (friendly, curious, cautious)
- **Best of both:** Structured progression + flexible themes

### Hybrid 3: Goal Stack + Momentum
- Use goal stack for character plans
- Use momentum to show "how" they pursue goals
- **Best of both:** Strategic depth + tactical variety

---

## Recommendations by Use Case

### Use Case: "I want seamless, natural continuation with minimal work"
→ **Approach 3: LLM-Driven Narrative Memory**
- Zero database changes
- Just prompt engineering
- Trust the LLM to maintain continuity

### Use Case: "I want trackable progress bars and explicit stages"
→ **Approach 1: Explicit Intent System**
- Show player "Seduction: 60%"
- Define clear stages (flirting → touching → intimate)
- Full control over progression

### Use Case: "I want simple, flexible tracking without rigid templates"
→ **Approach 2: Momentum Vector System**
- One JSONB column
- Handles any action type
- Emergent behavior

### Use Case: "I want something in between explicit and implicit"
→ **Approach 4: Action Tags & Continuation Flags**
- Simple flags and tags
- Some trackability, some flexibility
- Easy to implement

### Use Case: "I want characters with layered, strategic goals"
→ **Approach 5: Goal Stack System**
- Hierarchical motivations
- Short/medium/long term planning
- Character depth

### Use Case: "I want the best of multiple approaches"
→ **Hybrid: Momentum + LLM** or **Intent + Tags**
- Combine strengths
- Cover weaknesses
- More complex but more powerful

---

## My Recommendation

Based on your game's needs (dark fantasy, character-driven, LLM-heavy), I recommend:

### **Option A: Start with LLM Memory (Approach 3), evolve to Hybrid**
1. **Phase 1:** Use LLM-Driven Memory (quick implementation, test if it works)
2. **Phase 2:** If needed, add Momentum Vectors for mathematical boosting
3. **Phase 3:** If needed, add Explicit Intents for key sequences (seduction, combat)

**Why:** Progressive enhancement. Start simple, add complexity only where needed.

### **Option B: Go with Momentum Vectors (Approach 2)**
- Simple, flexible, emergent
- Works with your existing draft system
- Single JSONB column
- Easy to tune and adjust

**Why:** Best balance of simplicity and effectiveness for your use case.

---

## Questions to Help You Decide

1. **Do you want players to SEE progress?** (e.g., "Seduction progress: 60%")
   - Yes → Explicit Intent or Goal Stack
   - No → Momentum, LLM Memory, or Tags

2. **How much database complexity are you comfortable with?**
   - Minimal → LLM Memory or Momentum
   - Some → Action Tags
   - High → Explicit Intent or Goal Stack

3. **Do you trust the LLM to maintain continuity?**
   - Yes → LLM Memory
   - No → Explicit Intent

4. **Do you want rigid templates (seduction stages) or flexible themes?**
   - Rigid templates → Explicit Intent
   - Flexible themes → Momentum or Tags

5. **How many simultaneous "threads" should a character track?**
   - One at a time → Explicit Intent
   - Multiple → Momentum or Tags

Answer these and I can give you a specific recommendation!
