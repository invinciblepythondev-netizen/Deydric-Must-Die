# Multi-Turn Action System Design

## Overview

This document describes the design for handling actions that span multiple turns, allowing characters to pursue ongoing goals with variety and allowing for interruption/deviation.

## Core Concepts

### 1. Active Intent
An **Active Intent** represents a character's ongoing multi-turn goal:
- **Intent Type**: What they're trying to do (seduce, intimidate, persuade, investigate, etc.)
- **Target**: Who or what they're focused on
- **Progress**: How far along they are (0-100%)
- **Intensity**: How strongly they're pursuing it (subtle, moderate, aggressive, desperate)
- **Approach Style**: How they're doing it (gentle, forceful, playful, serious, romantic, lustful)

### 2. Intent Momentum
When a character has an active intent, their next turn's action generation is **biased** toward continuing it:
- **60% of draft options**: Continue the intent with variety in execution
- **20% of draft options**: Escalate to next stage
- **20% of draft options**: Pause, redirect, or abandon

### 3. Variety in Continuation
"Continue the intent" doesn't mean repeating the same action. Instead:
- Same goal, different approach (verbal → physical → emotional)
- Same stage, different tactics (playful → serious, subtle → bold)
- Response to target's reaction (if target pulls away → be gentler; if target reciprocates → be bolder)

## Database Schema

```sql
-- Track active character intents
CREATE TABLE character.character_intent (
    intent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id),
    game_state_id UUID NOT NULL REFERENCES game.game_state(game_state_id),

    -- What they're doing
    intent_type TEXT NOT NULL, -- 'seduce', 'intimidate', 'persuade', 'investigate', 'combat'
    intent_description TEXT, -- Human-readable description

    -- Who/what they're targeting
    target_character_id UUID REFERENCES character.character(character_id),
    target_object TEXT, -- For non-character targets

    -- Progress tracking
    progress_level INTEGER DEFAULT 0 CHECK (progress_level >= 0 AND progress_level <= 100),
    current_stage TEXT, -- Current stage name (e.g., 'flirting', 'escalating_touch')

    -- Style and intensity
    intensity TEXT DEFAULT 'moderate', -- 'subtle', 'moderate', 'aggressive', 'desperate'
    approach_style TEXT, -- 'gentle', 'forceful', 'playful', 'serious', 'romantic', 'lustful'

    -- Temporal tracking
    started_turn INTEGER NOT NULL,
    last_action_turn INTEGER NOT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    completion_status TEXT, -- NULL (ongoing), 'achieved', 'abandoned', 'interrupted', 'rejected'
    completion_turn INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),

    -- One active intent per character per target
    UNIQUE(character_id, game_state_id, intent_type, target_character_id)
);

CREATE INDEX idx_character_intent_active
    ON character.character_intent(character_id, game_state_id, is_active);
```

## Action Chain Templates

Common multi-turn action sequences with defined stages:

```python
ACTION_CHAINS = {
    'seduction': {
        'stages': [
            {
                'name': 'show_interest',
                'progress': (0, 25),
                'keywords': ['smile', 'glance', 'compliment', 'laugh', 'notice'],
                'examples': [
                    'Make eye contact and smile warmly',
                    'Compliment their appearance',
                    'Laugh at their jokes'
                ]
            },
            {
                'name': 'flirt',
                'progress': (25, 50),
                'keywords': ['flirt', 'tease', 'touch lightly', 'move closer', 'whisper'],
                'examples': [
                    'Playfully tease them',
                    'Touch their arm lightly while talking',
                    'Move closer and whisper'
                ]
            },
            {
                'name': 'escalate_touch',
                'progress': (50, 75),
                'keywords': ['caress', 'hold', 'stroke', 'embrace', 'lean in'],
                'examples': [
                    'Caress their face gently',
                    'Hold their hand',
                    'Pull them into an embrace'
                ]
            },
            {
                'name': 'intimate',
                'progress': (75, 100),
                'keywords': ['kiss', 'undress', 'bed', 'passionate', 'desire'],
                'examples': [
                    'Kiss them passionately',
                    'Begin removing clothing',
                    'Lead them to bed'
                ]
            }
        ]
    },

    'intimidation': {
        'stages': [
            {
                'name': 'verbal_threat',
                'progress': (0, 25),
                'keywords': ['threaten', 'warn', 'glare', 'raise voice'],
                'examples': [
                    'Threaten them verbally',
                    'Glare menacingly',
                    'Raise voice in warning'
                ]
            },
            {
                'name': 'physical_posturing',
                'progress': (25, 50),
                'keywords': ['step forward', 'loom', 'block', 'tower over'],
                'examples': [
                    'Step aggressively into their space',
                    'Loom over them menacingly',
                    'Block their exit'
                ]
            },
            {
                'name': 'physical_contact',
                'progress': (50, 75),
                'keywords': ['grab', 'shove', 'pin', 'seize'],
                'examples': [
                    'Grab them by the collar',
                    'Shove them against the wall',
                    'Pin their arm behind their back'
                ]
            },
            {
                'name': 'violence',
                'progress': (75, 100),
                'keywords': ['strike', 'punch', 'attack', 'choke', 'stab'],
                'examples': [
                    'Strike them across the face',
                    'Attack with weapon',
                    'Choke them'
                ]
            }
        ]
    },

    'persuasion': {
        'stages': [
            {
                'name': 'establish_rapport',
                'progress': (0, 25),
                'keywords': ['agree', 'common ground', 'empathize', 'listen'],
                'examples': [
                    'Find common ground',
                    'Show empathy for their position',
                    'Listen carefully to their concerns'
                ]
            },
            {
                'name': 'present_argument',
                'progress': (25, 50),
                'keywords': ['explain', 'reasoning', 'evidence', 'benefits'],
                'examples': [
                    'Explain your reasoning clearly',
                    'Present supporting evidence',
                    'Highlight the benefits'
                ]
            },
            {
                'name': 'handle_objections',
                'progress': (50, 75),
                'keywords': ['address concerns', 'compromise', 'alternative'],
                'examples': [
                    'Address their concerns directly',
                    'Offer a compromise',
                    'Suggest an alternative approach'
                ]
            },
            {
                'name': 'close',
                'progress': (75, 100),
                'keywords': ['agreement', 'commit', 'seal', 'decide'],
                'examples': [
                    'Request their agreement',
                    'Ask them to commit',
                    'Propose immediate action'
                ]
            }
        ]
    },

    'investigation': {
        'stages': [
            {
                'name': 'survey',
                'progress': (0, 25),
                'keywords': ['look around', 'scan', 'observe', 'examine room'],
                'examples': [
                    'Look around the area carefully',
                    'Scan for anything unusual',
                    'Observe the scene'
                ]
            },
            {
                'name': 'search',
                'progress': (25, 50),
                'keywords': ['search', 'check', 'look through', 'examine'],
                'examples': [
                    'Search through drawers',
                    'Check under furniture',
                    'Examine documents'
                ]
            },
            {
                'name': 'analyze',
                'progress': (50, 75),
                'keywords': ['study', 'analyze', 'piece together', 'deduce'],
                'examples': [
                    'Analyze the clues',
                    'Piece together information',
                    'Study the evidence carefully'
                ]
            },
            {
                'name': 'conclude',
                'progress': (75, 100),
                'keywords': ['conclude', 'realize', 'understand', 'discover'],
                'examples': [
                    'Draw conclusions',
                    'Realize the truth',
                    'Discover the hidden meaning'
                ]
            }
        ]
    }
}
```

## Integration with Action Generator

### Modified Draft Generation

When generating draft options, the system checks for active intents:

```python
# In ActionGenerationContext.build():
active_intent = get_active_intent(db_session, character['character_id'], game_state_id)

if active_intent:
    context['active_intent'] = {
        'type': active_intent.intent_type,
        'target': active_intent.target_name,
        'progress': active_intent.progress_level,
        'intensity': active_intent.intensity,
        'approach': active_intent.approach_style,
        'current_stage': active_intent.current_stage
    }
```

### Draft Prompt with Intent Awareness

```python
if active_intent:
    prompt += f"""

ACTIVE ONGOING INTENT:
Character is currently pursuing: {active_intent['type']} toward {active_intent['target']}
Current progress: {active_intent['progress']}% ({active_intent['current_stage']} stage)
Approach style: {active_intent['approach']}, Intensity: {active_intent['intensity']}

Generate {num_drafts} action ideas with this distribution:

CONTINUATION IDEAS (12 drafts, escalation_score -2 to +5):
- Continue the {active_intent['type']} intent with VARIETY in execution
- Same goal, different tactics (verbal, physical, emotional)
- Adapt based on target's previous response
- Examples: If currently at '{active_intent['current_stage']}' stage, stay there but vary approach

ESCALATION IDEAS (4 drafts, escalation_score +6 to +10):
- Advance to the next stage of {active_intent['type']}
- More intense, bolder, more direct actions
- Take the interaction to a deeper level

DIVERSION IDEAS (4 drafts, escalation_score -10 to -5):
- Pause the intent temporarily
- Switch to a different approach
- Respond to external factors or interruptions
"""
```

## Progress Tracking

### Automatic Progress Detection

After each action, the system detects if progress was made:

```python
def update_intent_progress(
    db_session,
    character_id: UUID,
    game_state_id: UUID,
    action_description: str,
    emotional_tone: str
):
    """Update intent progress based on action taken."""

    # Get active intent
    intent = get_active_intent(db_session, character_id, game_state_id)
    if not intent:
        return

    # Detect progress from action keywords
    progress_delta = detect_progress_from_action(
        intent.intent_type,
        action_description,
        emotional_tone
    )

    # Update progress
    new_progress = min(100, intent.progress_level + progress_delta)

    # Determine current stage
    chain = ACTION_CHAINS.get(intent.intent_type)
    current_stage = get_stage_from_progress(chain, new_progress)

    # Update database
    update_intent(
        db_session,
        intent.intent_id,
        progress_level=new_progress,
        current_stage=current_stage,
        last_action_turn=current_turn
    )

    # Check for completion
    if new_progress >= 100:
        complete_intent(db_session, intent.intent_id, status='achieved')
```

### Target Response Tracking

Track how the target responds to influence the continuation:

```python
# After target's turn, check if they're receptive
target_response = analyze_response(target_action)

if target_response == 'receptive':
    # Increase intensity or escalate faster
    adjust_intent_intensity(intent_id, intensity='aggressive')
elif target_response == 'resistant':
    # Back off or change approach
    adjust_intent_approach(intent_id, approach='gentle')
```

## Intent Lifecycle

### 1. Creation
Intent is created when:
- Character takes an action that starts a multi-turn sequence
- System detects keywords indicating intent start

### 2. Active
Intent remains active while:
- Character continues pursuing it each turn (or every few turns)
- Progress < 100%
- Not interrupted or abandoned

### 3. Dormant
Intent becomes dormant if:
- Character doesn't pursue it for 3+ turns
- Can be reactivated later

### 4. Completion
Intent completes when:
- **Achieved**: Progress reaches 100%
- **Rejected**: Target explicitly rejects
- **Abandoned**: Character gives up
- **Interrupted**: External event forces stop

## Example Flow

### Seduction Intent Over Multiple Turns

**Turn 1**: Character A decides to seduce Character B
```
Action: "Smile warmly at Character B and compliment their appearance"
→ Creates intent: type='seduction', target=B, progress=10%, stage='show_interest'
```

**Turn 2**: Intent influences draft generation
```
Draft options generated:
- [+3] Continue: Laugh at B's jokes and maintain eye contact (continuation, varied)
- [+5] Continue: Move to sit closer to B (continuation, escalation prep)
- [+8] Escalate: Playfully touch B's arm while talking (next stage: flirting)
- [-5] Divert: Turn attention to someone else (abandon intent)

Selected: [+5] Move to sit closer
→ Updates intent: progress=20%, stage='show_interest'
```

**Turn 3**: Intent continues
```
Draft options:
- [+5] Continue: Tease B playfully about something (entering flirt stage)
- [+7] Escalate: Touch B's hand gently (flirt stage)
- [+2] Continue: Whisper something amusing to B (show_interest with intimacy)
- [-3] Pause: React to someone else entering

Selected: [+7] Touch hand gently
→ Updates intent: progress=40%, stage='flirt'
```

**Turn 10**: High progress
```
progress=85%, stage='intimate'
Draft options heavily weighted toward intimate actions
Selected: "Pull B close and kiss them passionately"
→ Updates intent: progress=100%, status='achieved'
```

## Benefits

1. **Coherent Multi-Turn Narratives**: Actions feel connected and purposeful
2. **Variety**: Same goal pursued in different ways
3. **Organic Progression**: Natural escalation based on responses
4. **Interruptible**: Can pause or abandon intents
5. **Reactive**: Adapts to target's responses
6. **Mood-Aware**: Intent progression influences and is influenced by scene mood

## Implementation Priority

1. ✅ Database schema for character_intent table
2. ✅ Action chain template definitions
3. ✅ Get/set/update intent stored procedures
4. ✅ Modify ActionGenerationContext to include active_intent
5. ✅ Modify draft generation prompt with intent awareness
6. ✅ Progress detection and update after actions
7. ✅ Intent completion/abandonment logic
8. ⬜ Target response analysis
9. ⬜ Intent reactivation for dormant intents
10. ⬜ UI indicators showing active intents (optional)
