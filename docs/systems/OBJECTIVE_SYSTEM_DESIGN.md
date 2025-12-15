# Objective System - Design Overview

## Executive Summary

The hierarchical objective system enables characters to form goals, plan actions, and adapt behavior based on:
- **Personality-driven planning** (cognitive traits)
- **Dynamic re-prioritization** (mood, deadlines, context changes)
- **Hierarchical breakdown** (main → child → atomic objectives)
- **Recurring needs** (hunger, sleep, hygiene, social)
- **Delegation** (characters can assign tasks to each other)

This system makes character decisions more believable, goal-oriented, and responsive to the game world.

## Design Principles

### 1. Personality Matters

Different characters plan differently:
- **Methodical Planner**: Breaks objectives into many steps, plans far ahead
- **Impulsive**: Few objectives, abandons easily, immediate gratification
- **Detail-Oriented**: Deep objective hierarchies (5+ levels)
- **Scattered**: Many parallel objectives, low focus, switches frequently
- **Single-Minded**: One high-priority objective at a time, intense focus

**Implementation**: Cognitive traits with modifiers affecting:
- Planning capacity (max simultaneous objectives)
- Focus (resistance to abandonment/distraction)
- Max depth (how many levels of child objectives)
- Planning frequency (how often they re-evaluate)

### 2. Bounded Rationality

Characters have **cognitive limits**:
- Can't juggle unlimited objectives simultaneously
- Planning takes time (happens every N turns, not every turn)
- Fatigue/mood affects capacity (multipliers on limits)
- Low-priority objectives decay and are forgotten

**Why**: Prevents overwhelming complexity, creates realistic imperfection, makes characters relatable.

### 3. Hierarchical Planning

Objectives form trees:

```
Main: "Get revenge on Lord Deydric"
├── Child: "Gather evidence of his crimes"
│   ├── Atomic: "Search his office"
│   └── Atomic: "Interview witnesses"
├── Child: "Build alliances"
│   ├── Child: "Convince the blacksmith"
│   │   └── Atomic: "Help repair his forge"
│   └── Atomic: "Meet with the rebels"
└── Child: "Acquire a weapon"
    └── Atomic: "Purchase dagger from merchant"
```

**Depth control**: Personality traits limit how deep trees can go (1-5 levels).

**Atomic objectives**: Leaf nodes that can be completed in a single turn.

### 4. Dynamic Adaptation

Objectives aren't static:

**Re-evaluation triggers**:
- Every N turns (based on planning frequency)
- Cognitive overload (too many high-priority objectives)
- Major events (combat, betrayal, discovery)
- Deadline approaching
- Objective blocked

**Adjustments**:
- Priority changes (deadline → elevate priority)
- Status changes (blocked → create workaround child objective)
- New objectives (based on recent events)
- Abandonment (low priority + long inactive + low focus)

### 5. Needs Drive Behavior

Recurring objectives represent **biological/social needs**:
- Sleep (6-8 hours per day)
- Hunger (eat every ~15 turns)
- Hygiene (bathe/clean periodically)
- Social interaction (personality-dependent frequency)

**Priority escalation**: As need intensifies, priority increases:
- Hunger at 50% → low priority
- Hunger at 70% → high priority
- Hunger at 90% → critical priority

**Completion**: Needs can be partially satisfied (ate a snack = 0.2 progress vs full meal = 1.0 progress).

## Key Features

### 1. Delegation System

Character A can delegate tasks to Character B:

```python
# Character A's perspective
delegator_objective = {
    "description": "Ensure B fetches herbs from forest",
    "type": "main",
    "confirmation_required": True,
    "delegated_to_character_id": B_id
}

# Character B's perspective
delegated_objective = {
    "description": "Fetch herbs from forest",
    "type": "delegated",
    "delegated_from_character_id": A_id
}
```

**Confirmation flow**:
1. B completes task → marks as `waiting_confirmation`
2. A sees completion → confirms objective
3. Both objectives marked as `completed`

**Why**: Enables complex social interactions, emergent gameplay (characters asking favors, trade, loyalty).

### 2. Deadline System

Objectives can have two types of deadlines:

**Soft deadline** ("should complete by"):
- Passes → priority escalates
- Example: "Deliver message by evening" → evening comes → priority: medium → high

**Hard deadline** ("must complete by"):
- Passes → objective fails (status: abandoned)
- Mood penalty applied
- Example: "Save character before execution" → execution time → too late

### 3. Completion Cascades

When all child objectives complete → parent auto-completes:

```
Main: "Prepare for journey" (40% complete)
├── Child: "Pack supplies" (COMPLETED)
├── Child: "Repair boots" (COMPLETED)
└── Child: "Say goodbye to family" (COMPLETED)
→ Main auto-completes → 100%
```

**Mood impact**: Completing main objective → bigger mood boost than completing child.

### 4. Progress Tracking

Non-atomic objectives have **partial completion** (0.0 - 1.0):

- Navigation: "Travel to town" → each step toward town = +0.25 progress
- Gathering: "Collect 10 herbs" → each herb = +0.1 progress
- Relationship: "Befriend the merchant" → each positive interaction = +0.2 progress

**Automatic completion**: When progress reaches 1.0 → status changes to `completed`.

### 5. Decay & Forgetting

Low-importance objectives can be **forgotten**:

```python
objective = {
    "priority": "low",
    "decay_after_turns": 20,
    "turns_inactive": 0  # Increments each turn without progress
}

# After 20 turns of no progress → status: abandoned
```

**Why**: Simulates realistic forgetting, prevents objective clutter, allows characters to adapt.

## LLM Integration Points

### 1. Initial Objective Generation

When creating a character:

```python
LLM Input:
- Character profile (motivations, personality, backstory)
- Starting location/situation

LLM Output:
- 2-4 main objectives with priorities
- Success criteria for each
- Mood impact values
```

### 2. Objective Breakdown

When an objective needs sub-steps:

```python
LLM Input:
- Parent objective description
- Character profile
- Current situation (location, resources, relationships)

LLM Output:
- 2-5 child objectives
- Which are atomic (single-turn completion)
- Decay timers for each
```

### 3. Objective Re-evaluation

Periodically (every N turns):

```python
LLM Input:
- Current active objectives (5-10 max to avoid token overflow)
- Character state (mood, fatigue, location)
- Recent events

LLM Output:
- Priority changes (with reasons)
- Status changes (blocked, completed, abandoned)
- New objectives to create
- Suggestions for which to break down
```

### 4. Event-Driven Objectives

When something happens (dialogue, discovery, etc.):

```python
LLM Input:
- Event description
- Character involved
- Context

LLM Output:
- Should this create a new objective? (yes/no)
- If yes: objective details
```

## Performance Optimizations

### 1. Lazy Evaluation

Don't re-evaluate all objectives every turn:
- Use `planning_frequency_turns` (default: 5)
- Only evaluate high-priority objectives more frequently
- Batch evaluations (evaluate 5-10 at once, not one-by-one)

### 2. Denormalized Counters

`character_planning_state` table caches:
- Current objective counts by priority
- Computed planning capacity

**Why**: Avoids expensive COUNT queries on every turn.

**Update**: Trigger-based or explicit calls after objective add/remove.

### 3. Limited LLM Calls

**Expensive operations** (use LLM):
- Initial objective generation
- Objective breakdown
- Re-evaluation (every 5+ turns)
- Event-driven objective creation

**Cheap operations** (use rules):
- Deadline checking
- Decay/abandonment
- Completion cascades
- Priority escalation (needs-based)

### 4. Caching

Cache LLM responses for:
- Similar objective breakdowns (embeddings for similarity)
- Common recurring objective descriptions
- Typical re-evaluation patterns

## Edge Cases & Design Decisions

### Issue: Endless Planning

**Problem**: Character with "Methodical Planner" trait could spend entire turn planning instead of acting.

**Solution**:
- Planning happens in separate phase, not during action selection
- Planning limited by cognitive capacity (max N objectives evaluated per turn)
- Personality trait affects planning *frequency*, not planning *time*

### Issue: Objective Loops

**Problem**: Child objective could accidentally reference parent, creating a loop.

**Solution**:
- Database constraint: `parent_objective_id` foreign key with NO CYCLE check
- Service layer: Track depth, reject if exceeds max
- PostgreSQL recursive CTE with cycle detection

### Issue: Conflicting Objectives

**Problem**: "Kill Character A" and "Protect Character A" both active.

**Solution**:
- LLM re-evaluation detects conflicts
- Personality-dependent resolution:
  - High intelligence → recognizes conflict, abandons one
  - Low intelligence → doesn't notice, creates interesting behavior
- Mark conflicting objectives in metadata for UI display

### Issue: Delegation Spam

**Problem**: Character A delegates 50 tasks to Character B.

**Solution**:
- Cognitive capacity limits apply to delegated objectives too
- B can **refuse** tasks (requires action or automatic refusal if overloaded)
- A's planning state includes "pending confirmations" counter

### Issue: Stale Objectives

**Problem**: Objective becomes impossible (target character dies, location destroyed).

**Solution**:
- Evaluator checks for blocked conditions every turn
- Status → `blocked`
- LLM re-evaluation suggests either:
  - Abandon objective
  - Create workaround child objective

## Future Enhancements

### 1. Objective Templates Library

Pre-made templates for common objectives:
- "Travel to [location]" → auto-generates navigation child objectives
- "Gather [item] x N" → auto-tracks count in metadata
- "Build relationship with [character]" → tracks interaction quality

### 2. Conditional Objectives

Dependencies between objectives:
```python
objective = {
    "description": "Confront Lord Deydric",
    "prerequisites": ["gather_evidence", "build_alliances"],
    "status": "waiting"  # Can't start until prerequisites complete
}
```

### 3. Shared Objectives

Multiple characters working toward same objective:
```python
objective = {
    "description": "Defend the village",
    "character_ids": [A_id, B_id, C_id],
    "shared": True,
    "contributions": {A_id: 0.4, B_id: 0.3, C_id: 0.3}
}
```

### 4. Objective Templates from Game Events

Auto-generate objectives when events occur:
- Character insulted → create "Get revenge on [character]"
- Item stolen → create "Recover stolen [item]"
- Location discovered → create "Explore [location]"

### 5. Objective Journal (UI)

Player-visible objective tracker:
- Active main objectives
- Progress bars
- Current child objective being pursued
- Option to "suggest" objectives to NPCs

### 6. Objective-Based Dialogue

NPC dialogue references their objectives:
```
Player: "What are you doing?"
NPC: "I'm trying to gather evidence against Lord Deydric. (active main objective)"
```

## Cost Estimation

**Per character, per 10 turns**:
- 1 re-evaluation call (Haiku): ~500 tokens = $0.0004
- 0-2 breakdown calls (Haiku): ~300 tokens each = $0.0005
- Total: ~$0.001 per character per 10 turns

**For 10 AI characters in a 100-turn game**:
- 10 characters × 10 re-evaluations × $0.001 = $0.10

**Optimization**: Use Claude Haiku for all objective operations (10x cheaper than Sonnet).

## Summary

The objective system provides:
- **Personality-driven behavior** (cognitive traits → planning styles)
- **Realistic goal-seeking** (hierarchical objectives, bounded rationality)
- **Dynamic adaptation** (re-evaluation, priority changes, decay)
- **Biological needs** (recurring objectives for sleep, hunger, etc.)
- **Social complexity** (delegation, confirmation, shared goals)

**Result**: Characters feel alive, purposeful, and believable — not just reactive, but proactive with their own agendas.

---

**Next Steps**: See `OBJECTIVE_SYSTEM_INTEGRATION.md` for implementation guide.
