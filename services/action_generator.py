"""
Action Generation Service

Generates action options for characters using LLMs with:
- Multi-action sequences (think → speak → act)
- Mood awareness and escalation/de-escalation
- Context-appropriate diversity
- Proper public/private action tracking
- Automatic provider fallback for content policy handling
"""

import logging
import json
import random
from typing import List, Dict, Any, Optional
from uuid import UUID

from models.action_sequence import (
    ActionSequence, ActionOption, GeneratedActionOptions,
    SingleAction, ActionType, create_simple_action
)
from models.scene_mood import SceneMood
from models.game_time import GameTime
from models.turn import Turn
from services.context_manager import build_character_context, ContextPriority, _get_adaptive_memory_window
from sqlalchemy import text

# Import for proper error handling of provider fallback
try:
    from services.llm.resilient_generator import AllProvidersFailedError
except ImportError:
    # Fallback if not available
    class AllProvidersFailedError(Exception):
        pass

logger = logging.getLogger(__name__)


class ActionGenerationContext:
    """
    Assembles context specifically for action generation prompts.

    This is more focused than general character context - includes only
    what's needed for generating action options.
    """

    def __init__(
        self,
        db_session,
        character: Dict[str, Any],
        game_state_id: UUID,
        location: Dict[str, Any],
        visible_characters: List[Dict[str, Any]],
        current_turn: int,
        llm_provider=None
    ):
        self.db_session = db_session
        self.character = character
        self.game_state_id = game_state_id
        self.location = location
        self.visible_characters = visible_characters
        self.current_turn = current_turn
        self.llm_provider = llm_provider

    def _analyze_mood_from_actions(self, recent_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the mood/atmosphere dynamically from recent actions using LLM.
        Retries up to 2 times on invalid JSON responses.

        Args:
            recent_actions: List of recent action dictionaries

        Returns:
            Dictionary with mood_description and mood_guidance
        """
        if not recent_actions or not self.llm_provider:
            # Fallback to neutral mood
            return {
                'mood_description': "General mood: Neutral. The atmosphere is calm.",
                'mood_guidance': {
                    'should_generate_escalation': False,
                    'escalation_weight': 0.5,
                    'deescalation_required': False,
                    'mood_category': 'neutral'
                }
            }

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying mood analysis (attempt {attempt + 1}/{max_retries + 1})...")
                    print(f"🔄 Retrying mood analysis (attempt {attempt + 1}/{max_retries + 1})...")
                # Format recent actions for the LLM
                action_lines = []
                for action in recent_actions[-10:]:  # Last 10 actions max
                    action_lines.append(
                        f"Turn {action['turn_number']}: {action['character_name']} - {action['action_description']}"
                    )

                actions_text = "\n".join(action_lines)

                # Build prompt for mood analysis
                system_prompt = """You are an expert at analyzing emotional atmosphere and interpersonal dynamics in narrative scenes.

Analyze the recent actions and determine the current mood/atmosphere. Consider:
- Tension level (calm → tense → volatile)
- Romance level (neutral → flirtatious → passionate → intimate)
- Hostility level (friendly → irritated → hostile → violent)
- Overall emotional intensity

Return a JSON object with:
{
  "mood_description": "1-2 sentence description of the current atmosphere",
  "tension_level": "calm|moderate|high|volatile",
  "romance_level": "none|subtle|moderate|high|passionate",
  "hostility_level": "none|subtle|moderate|high",
  "should_escalate": true/false,
  "escalation_weight": 0.0-1.0,
  "mood_category": "neutral|tense|romantic|hostile|conflicted"
}"""

                user_prompt = f"""Analyze the mood from these recent actions:

{actions_text}

Current location: {self.location.get('name')}
Characters present: {', '.join([c.get('name') for c in self.visible_characters])}

What is the current emotional atmosphere?"""

                # Call LLM with automatic fallback
                response = self.llm_provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3,  # Lower temperature for consistent analysis
                    max_tokens=300
                )
                print("🎭 Mood analysis LLM response received (with resilient fallback)")

                # Parse response
                import re
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()

                # Clean up JSON
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                mood_data = json.loads(json_str)

                # Build mood description
                mood_description = mood_data.get('mood_description', 'The atmosphere is neutral.')

                # Convert to action guidance format
                should_escalate = mood_data.get('should_escalate', False)
                escalation_weight = float(mood_data.get('escalation_weight', 0.5))

                mood_guidance = {
                    'should_generate_escalation': should_escalate,
                    'escalation_weight': escalation_weight,
                    'deescalation_required': True,  # Always provide at least one de-escalation option
                    'mood_category': mood_data.get('mood_category', 'neutral')
                }

                logger.info(f"Dynamic mood analysis: {mood_data.get('mood_category')} (escalation_weight={escalation_weight:.2f})")

                # Success! Return result
                return {
                    'mood_description': mood_description,
                    'mood_guidance': mood_guidance
                }

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in mood analysis (attempt {attempt + 1}/{max_retries + 1}): {e}")
                print(f"⚠️  JSON decode error in mood analysis: {str(e)[:100]}")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    raise

            except AllProvidersFailedError as e:
                logger.error(
                    f"All providers failed for mood analysis: {e}",
                    exc_info=True
                )
                print(f"⚠️  All providers failed for mood analysis. Using neutral mood.")
                # Don't retry on provider failures - fallback immediately
                break

            except Exception as e:
                logger.error(
                    f"Error analyzing mood from actions (attempt {attempt + 1}/{max_retries + 1}): {e}",
                    exc_info=True
                )
                print(f"⚠️  Error in mood analysis: {str(e)[:100]}")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    break

        # All retries exhausted or provider failed - fallback to neutral mood
        logger.warning("Using neutral mood fallback after retries exhausted")
        return {
            'mood_description': "General mood: Neutral. The atmosphere is calm.",
            'mood_guidance': {
                'should_generate_escalation': False,
                'escalation_weight': 0.5,
                'deescalation_required': False,
                'mood_category': 'neutral'
            }
        }

    def build(self, model: str) -> Dict[str, Any]:
        """
        Build complete context for action generation.

        Returns dictionary with all context components.
        """
        context = {}

        # Time context
        time_context = GameTime.get_time_context(self.db_session, self.game_state_id)
        context['time_of_day'] = GameTime.format_time_for_prompt(time_context)
        context['lighting_description'] = GameTime.get_lighting_description(time_context)

        # Location
        context['location_name'] = self.location.get('name')
        context['location_description'] = self.location.get('description')

        # Character state
        context['character_name'] = self.character.get('name')
        context['character_emotional_state'] = self.character.get('current_emotional_state')
        context['character_motivations'] = self.character.get('motivations_short_term')

        # Visible characters (basic attributes only)
        context['visible_characters'] = []
        for char in self.visible_characters:
            context['visible_characters'].append({
                'name': char.get('name'),
                'appearance': char.get('physical_appearance'),
                'stance': char.get('current_stance'),
                'clothing': char.get('current_clothing')
            })

        # Working memory - fixed 4 turns (excluding atmospheric descriptions)
        memory_window = 4
        witnessed_actions = Turn.get_witnessed_memory(
            db_session=self.db_session,
            game_state_id=self.game_state_id,
            character_id=self.character['character_id'],
            last_n_turns=memory_window
        )

        # Filter out atmospheric actions from context
        witnessed_actions = [
            action for action in witnessed_actions
            if action.get('action_type') != 'atmospheric'
        ]

        # Mood - Will be analyzed inline during draft generation (no separate LLM call)
        # Fallback to database mood if needed
        mood = SceneMood.get(self.db_session, self.game_state_id, self.location['location_id'])
        if mood:
            context['mood_description'] = SceneMood.get_description(
                self.db_session,
                self.game_state_id,
                self.location['location_id']
            )
            context['mood_guidance'] = SceneMood.get_action_guidance(
                self.db_session,
                self.game_state_id,
                self.location['location_id']
            )
        else:
            context['mood_description'] = "General mood: Neutral. The atmosphere is calm."
            context['mood_guidance'] = {
                'should_generate_escalation': False,
                'escalation_weight': 0.5,
                'deescalation_required': False,
                'mood_category': 'neutral'
            }

        # Format working memory for prompt
        if witnessed_actions:
            memory_lines = []
            for action in witnessed_actions:
                memory_lines.append(
                    f"Turn {action['turn_number']}: {action['character_name']} - {action['action_description']}"
                )
            context['working_memory'] = "\n".join(memory_lines)
        else:
            context['working_memory'] = "No recent events to recall."

        # Event summaries (short-term summaries)
        summaries = self.db_session.execute(
            text("""
                SELECT * FROM memory_summary_get(
                    p_game_state_id := :game_state_id,
                    p_summary_type := 'short_term'
                )
                ORDER BY end_turn DESC
                LIMIT 3
            """),
            {"game_state_id": str(self.game_state_id)}
        ).fetchall()

        if summaries:
            summary_texts = [s.summary_text for s in summaries]
            context['event_summary'] = "\n\n".join(summary_texts)
        else:
            context['event_summary'] = None

        # Relationships with visible characters
        if self.visible_characters:
            relationships = []
            for char in self.visible_characters:
                rel = self.db_session.execute(
                    text("""
                        SELECT * FROM character_relationship_get(
                            p_source_character_id := :source_id,
                            p_target_character_id := :target_id
                        )
                    """),
                    {
                        "source_id": str(self.character['character_id']),
                        "target_id": str(char['character_id'])
                    }
                ).fetchone()

                if rel:
                    relationships.append(
                        f"{char['name']}: Trust {rel.trust:.1f}, Fear {rel.fear:.1f}, "
                        f"Respect {rel.respect:.1f} ({rel.relationship_type or 'neutral'})"
                    )

            if relationships:
                context['relationships'] = "\n".join(relationships)
            else:
                context['relationships'] = None
        else:
            context['relationships'] = None

        # Inventory (simple query, no stored procedure exists yet)
        inventory = self.db_session.execute(
            text("""
                SELECT item_name, quantity, item_properties
                FROM character.character_inventory
                WHERE character_id = :character_id
                ORDER BY item_name
            """),
            {"character_id": str(self.character['character_id'])}
        ).fetchall()

        if inventory:
            inventory_items = []
            for item in inventory:
                qty_str = f" x{item.quantity}" if item.quantity > 1 else ""
                inventory_items.append(f"{item.item_name}{qty_str}")
            context['inventory'] = ", ".join(inventory_items)
        else:
            context['inventory'] = None

        return context


class ActionGenerationPrompt:
    """
    Builds prompts for action generation with mood awareness.
    """

    @staticmethod
    def build_system_prompt(model: str = None) -> str:
        """
        Build system prompt for action generation.

        Args:
            model: Model identifier (optional, for context-aware prompt)

        Returns:
            System prompt string
        """
        from services.context_manager import ModelContextLimits

        # Determine if this is a small model (<=16K context)
        is_small_model = False
        if model:
            context_limit = ModelContextLimits.get_limit(model)
            is_small_model = context_limit <= 16384

        # Core action types (always included)
        core_actions = """- think: Private thought (only the character knows)
- speak: Public dialogue (others hear)
- interact: Interact with object/character
- move: Change location
- attack: Combat action
- steal: Take something covertly
- use_item: Use inventory item"""

        # Atmospheric action types (excluded for small models)
        atmospheric_actions = """- emote: Body language/gesture (others see)
- examine: Look at something closely
- wait: Do nothing/observe
- hide: Attempt stealth"""

        # Build action types list
        if is_small_model:
            action_types = core_actions
        else:
            action_types = core_actions + "\n" + atmospheric_actions

        return f"""You are an expert at generating character action options for a dark fantasy text adventure game.

Your task is to generate distinctive action options for a character's turn. Each option should be a SEQUENCE of actions that execute in order.

Action types available:
{action_types}

CRITICAL RULES:
1. Generate 5 distinctive options covering different emotional approaches
2. Each option can contain MULTIPLE actions in sequence (think → speak → act)
3. Always include at least ONE option that de-escalates the mood/tension
4. **ANTI-PLATEAU RULE**: Don't repeat the intensity level from previous actions. If escalation is needed, OPTIONS MUST PUSH THE SCENE FORWARD with concrete physical/verbal actions
5. Show internal thoughts (think actions) to reveal character psychology
6. Mix public and private actions appropriately

**ESCALATION MEANS TAKING ACTION, NOT JUST TALKING ABOUT IT:**

Romantic/Intimate scenes - escalation examples:
❌ BAD (plateau): "suggests they could get closer" / "talks about intimacy"
✅ GOOD (escalates): "moves closer and touches their face" / "begins removing an article of clothing" / "pulls them into an embrace" / "initiates a kiss"

Tense/Hostile scenes - escalation examples:
❌ BAD (plateau): "threatens them verbally" / "talks about fighting"
✅ GOOD (escalates): "grabs their arm forcefully" / "draws a weapon" / "shoves them against the wall" / "throws a punch"

Social/Political scenes - escalation examples:
❌ BAD (plateau): "hints at their secret" / "suggests an alliance"
✅ GOOD (escalates): "reveals the secret directly" / "makes a formal demand" / "offers a binding oath"

**When generating escalating options, characters must DO something concrete, not just talk about doing it.**

Format each option as JSON:
{{
  "summary": "Brief description of this approach",
  "emotional_tone": "cunning|aggressive|friendly|cautious|romantic|seductive|passionate|lustful|etc",
  "escalates_mood": true/false,
  "deescalates_mood": true/false,
  "estimated_mood_impact": {{"tension": +/-X, "hostility": +/-X, "romance": +/-X}},
  "turn_duration": 1-5 (number of turns to complete, 1 turn = ~30 seconds. Actions continuing from previous turn should have reduced duration),
  "actions": [
    {{"type": "think", "description": "...", "is_private": true}},
    {{"type": "speak", "description": "...", "is_private": false}},
    {{"type": "interact", "description": "...", "is_private": false, "target": "character_name"}}
  ]
}}

Return a JSON array of options."""

    @staticmethod
    def build_user_prompt(
        context: Dict[str, Any],
        num_escalation: int = None,
        num_neutral: int = None,
        num_deescalation: int = None,
        strong_escalation_mode: bool = None
    ) -> str:
        """
        Build user prompt with full context.

        Args:
            context: Context dictionary from ActionGenerationContext.build()
            num_escalation: Number of escalating options (calculated externally if using draft system)
            num_neutral: Number of neutral options
            num_deescalation: Number of de-escalating options
            strong_escalation_mode: Whether strong escalation is required

        Returns:
            Formatted prompt string
        """
        # Extract mood guidance first (needed throughout prompt building)
        mood_guidance = context['mood_guidance']
        escalation_needed = mood_guidance['should_generate_escalation']
        escalation_weight = mood_guidance['escalation_weight']
        mood_category = mood_guidance.get('mood_category', 'neutral')

        # Use provided escalation requirements if available (from draft selection)
        # Otherwise calculate them here (legacy behavior)
        if num_escalation is None or num_neutral is None or num_deescalation is None or strong_escalation_mode is None:
            print('mood_guidance:', mood_guidance)
            print('escalation_weight:', escalation_weight)

            # Calculate how many escalation vs neutral vs de-escalation options
            total_options = 5
            strong_escalation_mode = False

            if escalation_needed:
                # De-escalation: 20% chance for 1 de-escalation, 80% chance for STRONG escalation
                include_deescalation = random.random() < 0.2

                if include_deescalation:
                    # 20% case: Include 1 de-escalation option
                    num_deescalation = 1
                    # Escalation: 2-4 (randomized)
                    num_escalation = random.randint(2, 4)
                    # Neutral: make up the remainder
                    num_neutral = total_options - num_escalation - num_deescalation
                    strong_escalation_mode = False
                else:
                    # 80% case: STRONG ESCALATION MODE - no de-escalation, bold uninhibited actions
                    num_deescalation = 0
                    # More escalation options (2-4, all should be STRONG)
                    num_escalation = random.randint(2, 4)
                    # Neutral: make up the remainder
                    num_neutral = total_options - num_escalation
                    strong_escalation_mode = True
            else:
                num_escalation = 1
                num_deescalation = 1
                num_neutral = total_options - 2
                strong_escalation_mode = False
        else:
            # Using pre-calculated values from draft selection
            escalation_needed = (num_escalation > 1) or strong_escalation_mode

        total_options = num_escalation + num_neutral + num_deescalation
        prompt_parts = []

        # Character identity (relevant attributes only - handled by situational awareness)
        prompt_parts.append(f"CHARACTER: {context['character_name']}")
        prompt_parts.append(f"Emotional state: {context['character_emotional_state']}")
        prompt_parts.append(f"Current objectives: {context['character_motivations']}")

        # IMMEDIATE CONTEXT - Most recent action(s) for maximum relevance
        if context.get('working_memory'):
            # Extract just the most recent 1-2 actions
            memory_lines = context['working_memory'].split('\n')
            if memory_lines:
                immediate_actions = memory_lines[:2]  # Top 2 = most recent
                prompt_parts.append(f"\nIMMEDIATE CONTEXT (what just happened - DON'T REPEAT THIS INTENSITY LEVEL):")
                prompt_parts.append('\n'.join(immediate_actions))

                # Add explicit plateau warning during escalation
                if escalation_needed:
                    prompt_parts.append(
                        f"\n⚠️ The scene is escalating. Your options MUST go BEYOND what just happened above. "
                        f"Don't stay at the same level - PUSH FORWARD."
                    )

        # Time and location (abbreviated - full description not needed every turn)
        prompt_parts.append(f"\nTIME: {context['time_of_day']}")
        prompt_parts.append(f"LOCATION: {context['location_name']}")
        # Omit full location description to save tokens for recent actions

        # Mood
        prompt_parts.append(f"\nMOOD: {context['mood_description']}")

        # Other characters present
        if context['visible_characters']:
            prompt_parts.append("\nPRESENT CHARACTERS:")
            for char in context['visible_characters']:
                prompt_parts.append(
                    f"- {char['name']}: {char['appearance']}. "
                    f"Currently {char['stance']}. Wearing {char['clothing']}."
                )
        else:
            prompt_parts.append("\nNo other characters present.")

        # Relationships with present characters
        if context.get('relationships'):
            prompt_parts.append(f"\nRELATIONSHIPS:")
            prompt_parts.append(context['relationships'])

        if escalation_needed:
            if strong_escalation_mode:
                prompt_parts.append(
                    f"\n🔥 STRONG ESCALATION REQUIRED 🔥\n"
                    f"Generate {num_escalation} options with BOLD, UNINHIBITED actions that drive the {mood_category} mood to GREATER PASSION, "
                    f"and {num_neutral} neutral options.\n"
                    f"⚠️ CRITICAL: Strong escalation means going WELL BEYOND normal escalation actions. These should be DRAMATIC, DECISIVE moments that fundamentally change the dynamic."
                )
            else:
                prompt_parts.append(
                    f"\n⚡ ESCALATION REQUIRED ⚡\n"
                    f"Generate {num_escalation} options that ACTIVELY ESCALATE the {mood_category} mood, "
                    f"{num_neutral} neutral options, and {num_deescalation} option(s) that de-escalate."
                )

            # Add context-specific escalation guidance
            if mood_category in ['romantic', 'conflicted']:
                if strong_escalation_mode:
                    prompt_parts.append(
                        f"\n💋 STRONG ROMANTIC ESCALATION GUIDANCE:\n"
                        f"Normal escalation: touching, moving closer, gentle kisses\n"
                        f"STRONG escalation (REQUIRED): passionate embraces, urgent undressing, explicitly sexual actions, surrendering to desire completely\n"
                        f"- Go BEYOND tentative touches - be BOLD and PASSIONATE\n"
                        f"- Characters should act with URGENCY and ABANDON inhibitions\n"
                        f"- Take actions that are IRREVERSIBLE and cross major intimacy thresholds\n"
                        f"- Don't use 'step closer' or vague actions - be EXPLICIT about desire and intent\n"
                        f"- If already kissing, escalate to MORE: clothing removal, explicit touching, moving to bed, etc."
                    )
                else:
                    prompt_parts.append(
                        f"\n💋 ROMANTIC ESCALATION GUIDANCE:\n"
                        f"- Take PHYSICAL actions: touching, moving closer, removing clothing, embracing, kissing, or more sensual actions\n"
                        f"- Make BOLD requests or propositions, not hints\n"
                        f"- Show desire through ACTION, not just words\n"
                        f"- Don't plateau - if characters are already close, the next step is MORE intimate\n"
                        f"- Don't use 'step closer' or similar vague actions"
                    )
            elif mood_category == 'hostile':
                if strong_escalation_mode:
                    prompt_parts.append(
                        f"\n⚔️ STRONG HOSTILE ESCALATION GUIDANCE:\n"
                        f"Normal escalation: grabbing, shoving, drawing weapons\n"
                        f"STRONG escalation (REQUIRED): actual violence, brutal attacks, life-threatening actions, crossing the point of no return\n"
                        f"- Go BEYOND threats - ATTACK with full force\n"
                        f"- Actions should cause REAL harm and danger\n"
                        f"- Take actions that CANNOT be taken back\n"
                        f"- If weapons are drawn, USE them decisively"
                    )
                else:
                    prompt_parts.append(
                        f"\n⚔️ HOSTILE ESCALATION GUIDANCE:\n"
                        f"- Take PHYSICAL actions: grabbing, shoving, weapon-drawing, attacking\n"
                        f"- Make DIRECT threats or demands, not hints\n"
                        f"- Show aggression through ACTION, not just words\n"
                        f"- Don't plateau - if tension is high, violence or forceful action comes next"
                    )
            elif mood_category == 'tense':
                if strong_escalation_mode:
                    prompt_parts.append(
                        f"\n⚡ STRONG TENSION ESCALATION GUIDANCE:\n"
                        f"Normal escalation: revealing hints, making veiled demands\n"
                        f"STRONG escalation (REQUIRED): explosive revelations, ultimatums, power plays that force immediate consequences\n"
                        f"- REVEAL major secrets completely, not hints\n"
                        f"- Make ULTIMATUMS and demands with real stakes\n"
                        f"- Take actions that FORCE the other character to respond dramatically\n"
                        f"- Create moments of NO RETURN"
                    )
                else:
                    prompt_parts.append(
                        f"\n⚡ TENSION ESCALATION GUIDANCE:\n"
                        f"- Increase stakes with ACTIONS: revealing secrets, making demands, physical closeness\n"
                        f"- Take risks that change the power dynamic\n"
                        f"- Don't plateau - tension requires RELEASE through action or conflict"
                    )
        else:
            prompt_parts.append(
                f"\nGenerate {num_escalation} option(s) that could escalate, "
                f"{num_neutral} neutral options, and {num_deescalation} "
                f"option(s) that de-escalate."
            )

        prompt_parts.append(
            "\n🎭 ANTI-PLATEAU REQUIREMENT:\n"
            "DO NOT generate options that:\n"
            "- Repeat the same intensity as the most recent action\n"
            "- Just talk about doing something instead of doing it\n"
            "- Suggest or hint instead of taking concrete action\n"
            "- Stay at the current intimacy/tension level without progressing\n"
            "\nEach option must be DISTINCTIVE and move the scene in a clear direction."
        )

        # Working memory (past 5-10 turns) - full history for context
        if context.get('working_memory'):
            prompt_parts.append(f"\nRECENT EVENTS (full history, newest first):")
            prompt_parts.append(context['working_memory'])

        # Event summary (if available)
        if context.get('event_summary'):
            prompt_parts.append(f"\nSESSION SUMMARY:")
            prompt_parts.append(context['event_summary'])

        # Inventory
        if context.get('inventory'):
            prompt_parts.append(f"\nINVENTORY: {context['inventory']}")

        # Generation instructions based on mood
        print('escalation_needed:', escalation_needed)
        print('strong_escalation_mode:', strong_escalation_mode)

        # Include selected draft summaries as seed ideas (if available)
        if context.get('selected_draft_summaries'):
            prompt_parts.append(f"\n{'='*80}")
            prompt_parts.append(f"CRITICAL INSTRUCTION: EXPAND THESE {total_options} SELECTED ACTION IDEAS")
            prompt_parts.append(f"{'='*80}")
            prompt_parts.append("\nYou MUST expand each of the following action ideas into a full action sequence.")
            prompt_parts.append("DO NOT generate new ideas - ONLY expand the ones listed below:\n")
            for i, summary in enumerate(context['selected_draft_summaries'], 1):
                prompt_parts.append(f"  {i}. {summary}")
            prompt_parts.append("\nFor EACH idea above, create a complete action sequence with:")
            prompt_parts.append("- Private thought (think action) revealing character's internal state")
            prompt_parts.append("- Dialogue (speak action) if appropriate")
            prompt_parts.append("- Physical action (interact/emote/etc) bringing the idea to life")
            prompt_parts.append(f"\n{'='*80}\n")
        else:
            prompt_parts.append(f"\n--- GENERATE {total_options} DISTINCTIVE ACTION OPTIONS ---")

        prompt_parts.append("\nReturn a JSON array of options as specified in the system prompt.")

        return "\n".join(prompt_parts)


class ActionGenerator:
    """
    Generates action options for characters using LLMs with automatic provider fallback.

    PROVIDER FALLBACK SYSTEM:
    -------------------------
    All LLM calls in this class automatically use the ResilientActionGenerator
    fallback chain when llm_provider is a ResilientActionGenerator instance.

    The fallback chain handles:
    - Content policy violations (automatic retry with next provider)
    - API failures (automatic retry with next provider)
    - Provider-specific prompt adaptation
    - Graceful degradation to fallback options

    LLM CALLS WITH FALLBACK:
    1. _analyze_mood_from_actions() - Mood detection from recent actions
    2. _generate_draft_options() - Generate 20 varied draft options
    3. generate_options() - Final detailed action generation

    All calls will automatically try providers in this order:
    - Anthropic Claude (primary)
    - OpenAI GPT (fallback)
    - AIML API (permissive fallback)
    - Together.ai (backup)
    - Local models (if configured)

    ERROR HANDLING:
    - AllProvidersFailedError: Caught and fallback options provided
    - Generic exceptions: Caught and fallback options provided
    - All errors logged with provider chain information
    """

    def __init__(self, llm_provider):
        """
        Initialize action generator.

        Args:
            llm_provider: LLM provider instance (should be ResilientActionGenerator
                         for automatic fallback, but can be any provider with a
                         generate() method)
        """
        self.llm_provider = llm_provider
        self.prompt_builder = ActionGenerationPrompt()

        # Log provider type for debugging
        provider_type = type(llm_provider).__name__
        logger.info(f"ActionGenerator initialized with provider: {provider_type}")
        if "Resilient" not in provider_type:
            logger.warning(
                f"ActionGenerator initialized with non-resilient provider: {provider_type}. "
                "Consider using ResilientActionGenerator for automatic fallback."
            )

    def _generate_draft_options(
        self,
        context: Dict[str, Any],
        num_drafts: int = 20
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate draft action options with escalation scores AND inline mood analysis.
        Uses resilient provider fallback automatically.
        Retries up to 2 times on invalid JSON responses.

        This replaces the separate mood analysis LLM call by incorporating mood detection
        into the draft generation step.

        Args:
            context: Context dictionary from ActionGenerationContext.build()
            num_drafts: Number of draft options to generate

        Returns:
            Tuple of (draft_options_list, mood_guidance_dict)
        """
        # Extract key context for analysis
        immediate_context = ""
        character_last_turn = None
        others_actions_since = []

        if context.get('working_memory'):
            memory_lines = context['working_memory'].split('\n')
            if memory_lines:
                # Get last few actions for emotional tone analysis
                immediate_context = '\n'.join(memory_lines[:4])

                # Parse to find character's last turn and others' actions since
                for line in memory_lines:
                    if context['character_name'] in line:
                        if character_last_turn is None:
                            character_last_turn = line
                    elif character_last_turn is not None:
                        # This is after character's last turn
                        others_actions_since.append(line)

        # Build comprehensive prompt that does BOTH mood analysis AND draft generation
        draft_system_prompt = f"""You are generating action ideas for a character in a dark fantasy game.

Your task is TWO-FOLD:
1. Analyze the emotional tone/atmosphere from recent actions
2. Generate {num_drafts} diverse action ideas that proceed from the recent acctions and give each action idea an escalation score

For MOOD ANALYSIS, consider:
- Emotional tone of recent events (calm, tense, romantic, hostile, etc.)
- Escalation trajectory (de-escalating, stable, escalating)

For ACTION IDEAS, each turn represents ~30 seconds of in-game time. Actions that take longer should specify turn_duration > 1.

Return a JSON object with TWO sections:
{{
  "mood_analysis": {{
    "emotional_tone": "brief description of current emotional atmosphere",
    "mood_category": "a single descriptive word capturing the dominant mood (e.g., neutral, tense, romantic, hostile, playful, melancholic, anxious, passionate, suspicious, intimate, aggressive, fearful, joyful, etc.)",
    "should_escalate": true/false,
    "escalation_weight": 0.0-1.0
  }},
  "draft_options": [
    {{
      "summary": "1-2 sentence action description",
      "escalation_score": -10 to +10,
      "turn_duration": 1-5 (estimated turns to complete, default 1)
    }},
    ...{num_drafts} total...
  ]
}}"""

        # Build context-aware user prompt
        continuing_action_note = ""
        if character_last_turn:
            continuing_action_note = f"\nNOTE: Character's last action: {character_last_turn}"
            # Check if this might be a multi-turn action (we'll look for duration metadata later)
            continuing_action_note += f"\nIf this was a multi-turn action, include several options that CONTINUE it with reduced turn_duration."

        others_note = ""
        if others_actions_since:
            others_note = f"\nACTIONS BY OTHERS SINCE CHARACTER'S LAST TURN:\n" + '\n'.join(others_actions_since[:3])

        draft_user_prompt = f"""CHARACTER: {context['character_name']}
Emotional state: {context['character_emotional_state']}
Short-term objectives: {context['character_motivations']}

LOCATION: {context['location_name']}

RECENT EVENTS (for mood analysis and context):
{immediate_context if immediate_context else 'Scene is just beginning'}{continuing_action_note}{others_note}

OTHER CHARACTERS PRESENT:
{', '.join([c['name'] for c in context['visible_characters']]) if context['visible_characters'] else 'None'}

TASK:
1. Analyze the emotional tone/mood from the recent events
2. Generate {num_drafts} varied action ideas:
   - Range from strong de-escalation (-10) to strong escalation (+10)
   - Include mix across full spectrum
   - Consider character's objectives
   - Estimate turn_duration (1 turn = ~30 seconds)
   - If character was performing multi-turn action, include options to CONTINUE it

Return the JSON object as specified."""

        logger.info(f"Generating {num_drafts} draft options with inline mood analysis...")
        print(f"\n🎲 Generating {num_drafts} draft options with inline mood analysis (2-in-1 LLM call)...")

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying draft generation (attempt {attempt + 1}/{max_retries + 1})...")
                    print(f"🔄 Retrying draft generation (attempt {attempt + 1}/{max_retries + 1})...")

                # This automatically uses ResilientActionGenerator's fallback chain
                # if llm_provider is a ResilientActionGenerator (which it should be)
                response = self.llm_provider.generate(
                    system_prompt=draft_system_prompt,
                    user_prompt=draft_user_prompt,
                    temperature=0.8,  # High temperature for variety, but not too random
                    max_tokens=2000  # Increased for mood analysis + drafts
                )

                # Log the response for debugging
                logger.info(f"Draft generation response length: {len(response)} chars")
                logger.debug(f"Draft generation response: {response[:500]}...")
                print(f"📄 Draft response length: {len(response)} chars")

                # Check for empty response
                if not response or not response.strip():
                    raise ValueError("Empty response from LLM")

                # Parse response with multiple strategies
                import re
                json_str = response.strip()

                # Strategy 1: Extract from markdown code blocks
                if "```json" in json_str:
                    match = re.search(r'```json\s*(\{.*?\})\s*```', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                    else:
                        # Try simpler extraction
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    match = re.search(r'```\s*(\{.*?\})\s*```', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                    else:
                        json_str = json_str.split("```")[1].split("```")[0].strip()

                # Strategy 2: Find JSON object anywhere in response
                if not json_str.startswith('{'):
                    match = re.search(r'\{.*\}', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                    else:
                        raise ValueError("No JSON object found in response")

                # Clean up JSON
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas

                # Log what we're trying to parse
                logger.debug(f"Attempting to parse JSON: {json_str[:200]}...")
                print(f"🔍 Parsing JSON object ({len(json_str)} chars)...")

                result = json.loads(json_str)

                # Validate structure
                if not isinstance(result, dict):
                    raise ValueError(f"Expected dict, got {type(result)}")
                if 'mood_analysis' not in result or 'draft_options' not in result:
                    raise ValueError("Missing required sections: mood_analysis or draft_options")

                mood_analysis = result['mood_analysis']
                drafts = result['draft_options']

                if not isinstance(drafts, list) or len(drafts) == 0:
                    raise ValueError("draft_options must be non-empty list")

                # Convert mood_analysis to mood_guidance format
                mood_guidance = {
                    'should_generate_escalation': mood_analysis.get('should_escalate', False),
                    'escalation_weight': float(mood_analysis.get('escalation_weight', 0.5)),
                    'deescalation_required': True,  # Always provide de-escalation option
                    'mood_category': mood_analysis.get('mood_category', 'neutral')
                }

                logger.info(f"✓ Successfully generated {len(drafts)} draft options with mood analysis")
                logger.info(f"  Mood: {mood_guidance['mood_category']}, escalation_weight={mood_guidance['escalation_weight']:.2f}")
                print(f"✓ Parsed {len(drafts)} draft options successfully")
                print(f"🎭 Mood detected: {mood_guidance['mood_category']} (escalation_weight={mood_guidance['escalation_weight']:.2f})")
                print(f"🎭 Emotional tone: {mood_analysis.get('emotional_tone', 'N/A')}")

                return drafts, mood_guidance

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in draft generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.warning(f"Response was: {response[:500]}...")
                logger.warning(f"JSON string attempted: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
                print(f"⚠️  JSON decode error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200]}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    print(f"⚠️  All retry attempts exhausted. Using fallback drafts.")
                    break

            except AllProvidersFailedError as e:
                logger.error(f"All providers failed for draft generation: {e}", exc_info=True)
                print(f"⚠️  All providers failed for draft generation. Using fallback drafts.")
                # Don't retry on provider failures - fallback immediately
                break

            except ValueError as e:
                logger.warning(f"Value error in draft generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.warning(f"Response was: {response[:500] if 'response' in locals() else 'N/A'}...")
                print(f"⚠️  Value error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200] if 'response' in locals() else 'N/A'}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    print(f"⚠️  All retry attempts exhausted. Using fallback drafts.")
                    break

            except Exception as e:
                logger.error(f"Error generating draft options (attempt {attempt + 1}/{max_retries + 1}): {e}", exc_info=True)
                logger.error(f"Response was: {response[:500] if 'response' in locals() else 'N/A'}...")
                print(f"⚠️  Error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200] if 'response' in locals() else 'N/A'}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    break

        # All retries exhausted or provider failed - return fallback drafts
        logger.warning("Using fallback drafts after retries exhausted")
        fallback_mood_guidance = {
            'should_generate_escalation': False,
            'escalation_weight': 0.5,
            'deescalation_required': True,
            'mood_category': 'neutral'
        }
        fallback_drafts = [
            {"summary": "Wait and observe the situation", "escalation_score": 0, "turn_duration": 1},
            {"summary": "Speak calmly to de-escalate", "escalation_score": -5, "turn_duration": 1},
            {"summary": "Take a cautious neutral action", "escalation_score": -1, "turn_duration": 1},
            {"summary": "Take a bold forward action", "escalation_score": 5, "turn_duration": 1},
            {"summary": "Escalate the situation decisively", "escalation_score": 8, "turn_duration": 1}
        ]
        return fallback_drafts, fallback_mood_guidance

    def _select_drafts_by_requirements(
        self,
        drafts: List[Dict[str, Any]],
        num_escalation: int,
        num_neutral: int,
        num_deescalation: int
    ) -> List[Dict[str, Any]]:
        """
        Select draft options based on escalation requirements.
        Ensures no duplicates are selected.

        Args:
            drafts: List of draft options with escalation_score
            num_escalation: Number of escalating options needed
            num_neutral: Number of neutral options needed
            num_deescalation: Number of de-escalating options needed

        Returns:
            Selected subset of drafts (no duplicates)
        """
        # Sort by escalation score
        sorted_drafts = sorted(drafts, key=lambda d: d.get('escalation_score', 0))

        # Categorize drafts
        deescalating = [d for d in sorted_drafts if d.get('escalation_score', 0) < -2]
        neutral = [d for d in sorted_drafts if -2 <= d.get('escalation_score', 0) <= 2]
        escalating = [d for d in sorted_drafts if d.get('escalation_score', 0) > 2]

        selected = []
        selected_ids = set()  # Track IDs to prevent duplicates

        def add_unique(draft_list, count):
            """Add drafts ensuring no duplicates."""
            available = [d for d in draft_list if id(d) not in selected_ids]
            to_select = min(count, len(available))
            if to_select > 0:
                selected_drafts = random.sample(available, to_select)
                for draft in selected_drafts:
                    selected.append(draft)
                    selected_ids.add(id(draft))
                return to_select
            return 0

        def add_weighted_unique(draft_list, count):
            """Add drafts with weighted selection (bias to higher scores) ensuring no duplicates."""
            available = [d for d in draft_list if id(d) not in selected_ids]
            to_select = min(count, len(available))
            if to_select > 0:
                # Use weighted random selection without replacement
                weights = [d.get('escalation_score', 0) for d in available]
                selected_drafts = []
                available_copy = available.copy()
                weights_copy = weights.copy()

                for _ in range(to_select):
                    if not available_copy:
                        break
                    # Normalize weights to be positive for random.choices
                    min_weight = min(weights_copy)
                    if min_weight < 0:
                        normalized_weights = [w - min_weight + 1 for w in weights_copy]
                    else:
                        normalized_weights = [w + 1 for w in weights_copy]  # +1 to avoid zero weights

                    chosen = random.choices(available_copy, weights=normalized_weights, k=1)[0]
                    selected_drafts.append(chosen)

                    # Remove chosen from available pool
                    idx = available_copy.index(chosen)
                    available_copy.pop(idx)
                    weights_copy.pop(idx)

                for draft in selected_drafts:
                    selected.append(draft)
                    selected_ids.add(id(draft))
                return len(selected_drafts)
            return 0

        # Select de-escalating (random from bottom scores)
        if num_deescalation > 0:
            add_unique(deescalating, num_deescalation)

        # Select escalating (random from top scores, with bias towards highest in strong mode)
        if num_escalation > 0:
            add_unique(escalating, num_escalation)

        # Select neutral (random from middle scores)
        if num_neutral > 0:
            add_unique(neutral, num_neutral)

        # If we don't have enough, pad with random drafts from any category
        target_count = num_escalation + num_neutral + num_deescalation
        while len(selected) < target_count:
            remaining = [d for d in drafts if id(d) not in selected_ids]
            if remaining:
                chosen = random.choice(remaining)
                selected.append(chosen)
                selected_ids.add(id(chosen))
            else:
                break

        # Final duplicate check using summary text as key (just in case)
        seen_summaries = set()
        deduplicated = []
        for draft in selected:
            summary = draft.get('summary', '')
            if summary not in seen_summaries:
                seen_summaries.add(summary)
                deduplicated.append(draft)
            else:
                logger.warning(f"Removed duplicate draft: {summary[:50]}...")

        return deduplicated

    def generate_options(
        self,
        db_session,
        character: Dict[str, Any],
        game_state_id: UUID,
        location: Dict[str, Any],
        visible_characters: List[Dict[str, Any]],
        current_turn: int,
        num_options: int = 5
    ) -> GeneratedActionOptions:
        """
        Generate action options for a character's turn.

        Uses automatic provider fallback for content policy handling:
        1. Generates 20 draft options with escalation scores
        2. Selects best subset based on mood requirements
        3. Generates detailed options from selected drafts

        All LLM calls use ResilientActionGenerator for automatic fallback
        through the provider chain if content is refused.

        Args:
            db_session: Database session
            character: Character profile dictionary
            game_state_id: Game state UUID
            location: Location dictionary
            visible_characters: List of character dictionaries
            current_turn: Current turn number
            num_options: Number of options to generate

        Returns:
            GeneratedActionOptions containing all generated options
        """
        print("ActionGenerator generate_options (with resilient fallback)")
        logger.info(
            f"Generating {num_options} action options for {character.get('name')} "
            f"at turn {current_turn} (using resilient provider fallback)"
        )

        # Build context
        context_builder = ActionGenerationContext(
            db_session,
            character,
            game_state_id,
            location,
            visible_characters,
            current_turn,
            llm_provider=self.llm_provider
        )
        context = context_builder.build(model=self.llm_provider.model_name)

        #print('Generated context for action generation:', context)
        print('Initial mood guidance (from DB):', context['mood_guidance'])

        # STAGE 1: Generate draft options with escalation scores AND inline mood analysis (2-in-1)
        draft_options, mood_guidance = self._generate_draft_options(context, num_drafts=20)

        # Override context mood_guidance with LLM-analyzed mood
        context['mood_guidance'] = mood_guidance

        # Print draft options for monitoring
        print(f"\n📋 Generated {len(draft_options)} draft options:")
        for i, draft in enumerate(draft_options, 1):
            score = draft.get('escalation_score', 0)
            duration = draft.get('turn_duration', 1)
            emoji = "🔥" if score >= 6 else "⚡" if score > 2 else "➡️" if score >= -2 else "🕊️" if score > -6 else "❄️"
            duration_str = f" ({duration}T)" if duration > 1 else ""
            print(f"  {i:2d}. [{score:+3d}] {emoji} {draft.get('summary', 'No summary')}{duration_str}")
        escalation_needed = mood_guidance['should_generate_escalation']
        escalation_weight = mood_guidance['escalation_weight']

        # Calculate requirements (from build_user_prompt logic)
        total_options = 5

        if escalation_needed:
            include_deescalation = random.random() < 0.2

            if include_deescalation:
                num_deescalation = 1
                num_escalation = random.randint(2, 4)
                num_neutral = total_options - num_escalation - num_deescalation
            else:
                num_deescalation = 0
                num_escalation = random.randint(3, 4)
                num_neutral = total_options - num_escalation

        else:
            num_escalation = 1
            num_deescalation = 1
            num_neutral = total_options - 2

        # STAGE 2: Select subset based on requirements
        selected_drafts = self._select_drafts_by_requirements(
            draft_options,
            num_escalation,
            num_neutral,
            num_deescalation
        )

        # Print selected drafts
        print(f"\n✅ Selected {len(selected_drafts)} drafts for final generation:")
        print(f"   Escalating: {num_escalation}, Neutral: {num_neutral}, De-escalating: {num_deescalation}")

        for i, draft in enumerate(selected_drafts, 1):
            score = draft.get('escalation_score', 0)
            emoji = "🔥" if score >= 6 else "⚡" if score > 2 else "➡️" if score >= -2 else "🕊️"
            print(f"  {i}. [{score:+3d}] {emoji} {draft.get('summary', 'No summary')}")

        # Add selected drafts to context for final generation
        context['selected_draft_summaries'] = [d.get('summary') for d in selected_drafts]

        # Build prompts (pass pre-calculated escalation requirements)
        system_prompt = self.prompt_builder.build_system_prompt(model=self.llm_provider.model_name)
        user_prompt = self.prompt_builder.build_user_prompt(
            context,
            num_escalation=num_escalation,
            num_neutral=num_neutral,
            num_deescalation=num_deescalation
        )

        logger.debug(f"System prompt: {system_prompt[:200]}...")
        logger.debug(f"User prompt: {user_prompt[:500]}...")

        #print(f"System prompt: {system_prompt[:200]}...")
        print(f"\n📝 User prompt length: {len(user_prompt)} chars")
        print(f"📝 System prompt length: {len(system_prompt)} chars")

        # Call LLM
        try:
            # Check if provider is ResilientActionGenerator (has built-in action generation)
            if hasattr(self.llm_provider, 'generate_action_options'):
                # Use resilient action generation with built-in parsing and fallback
                logger.info("Using ResilientActionGenerator.generate_action_options()")
                print("Using ResilientActionGenerator.generate_action_options()")
                options_dicts = self.llm_provider.generate_action_options(
                    character=character,
                    context=context,
                    num_options=num_options
                )

                # Convert to ActionOption objects
                options = []
                for idx, opt in enumerate(options_dicts, start=1):
                    # Build actions from the dict
                    actions = []

                    # Handle different response formats
                    if opt.get('private_thought'):
                        actions.append(SingleAction(
                            action_type=ActionType.THINK,
                            description=opt['private_thought'],
                            is_private=True
                        ))
                    if opt.get('dialogue') or opt.get('speech'):
                        actions.append(SingleAction(
                            action_type=ActionType.SPEAK,
                            description=opt.get('dialogue') or opt.get('speech'),
                            is_private=False
                        ))
                    if opt.get('action'):
                        actions.append(SingleAction(
                            action_type=ActionType.INTERACT,
                            description=opt['action'],
                            is_private=False
                        ))

                    if actions:
                        sequence = ActionSequence(
                            actions=actions,
                            summary=opt.get('summary', f'Option {idx}'),
                            escalates_mood=False,
                            deescalates_mood=False,
                            emotional_tone='neutral'
                        )
                        options.append(ActionOption(
                            option_id=idx,
                            sequence=sequence,
                            selection_weight=1.0
                        ))
            else:
                # Use generic generate method (with resilient fallback if provider supports it)
                # Retry up to 2 times on JSON parsing errors
                logger.info("Using LLM provider.generate() with resilient fallback")
                print("🔄 Using LLM provider.generate() (automatic fallback enabled)")

                max_retries = 2
                options = None
                for attempt in range(max_retries + 1):
                    try:
                        if attempt > 0:
                            logger.info(f"Retrying action generation (attempt {attempt + 1}/{max_retries + 1})...")
                            print(f"🔄 Retrying action generation (attempt {attempt + 1}/{max_retries + 1})...")

                        response = self.llm_provider.generate(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=0.8,  # More creative for diverse options
                            max_tokens=2048
                        )

                        logger.debug(f"LLM response: {response[:500]}...")

                        # Parse response into action sequences
                        options = self._parse_response(response, context)

                        # Success!
                        break

                    except (json.JSONDecodeError, ValueError) as e:
                        error_type = "JSON decode" if isinstance(e, json.JSONDecodeError) else "parsing"
                        logger.warning(f"{error_type} error in action generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        print(f"⚠️  {error_type} error in action generation: {str(e)[:100]}")
                        if attempt < max_retries:
                            continue  # Retry
                        else:
                            # Final attempt failed, re-raise to be caught by outer exception handler
                            raise

                if options is None:
                    # This shouldn't happen, but just in case
                    raise ValueError("Failed to generate options after retries")

            # Validate we have required de-escalation option
            #deescalation_options = [opt for opt in options if opt.sequence.deescalates_mood]
            #if not deescalation_options:
            #    logger.warning("No de-escalation option generated, adding fallback")
            #    options.append(self._create_fallback_deescalation(character, location))

            # Create result
            result = GeneratedActionOptions(
                character_id=str(character.get('character_id')),
                turn_number=current_turn,
                options=options,
                mood_category=context['mood_guidance']['mood_category'],  # String from LLM mood analysis
                generation_context=context
            )

            logger.info(
                f"Successfully generated {len(options)} options for {character.get('name')}"
            )

            return result

        except AllProvidersFailedError as e:
            logger.error(f"All providers failed for action generation: {e}", exc_info=True)
            print(f"⚠️  All providers failed. Using fallback action options.")
            print(f"    Attempted providers: {', '.join(e.attempted_providers) if hasattr(e, 'attempted_providers') else 'unknown'}")
            # Return fallback options
            return self._create_fallback_options(
                character,
                location,
                current_turn,
                context
            )

        except Exception as e:
            logger.error(f"Error generating action options: {e}", exc_info=True)
            print(f"⚠️  Error in action generation: {str(e)[:100]}")
            print("    Falling back to default action options.")
            # Return fallback options
            return self._create_fallback_options(
                character,
                location,
                current_turn,
                context
            )

    def _parse_response(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[ActionOption]:
        """
        Parse LLM response into ActionOption objects.

        Args:
            response: Raw LLM response (should be JSON array)
            context: Generation context

        Returns:
            List of ActionOption objects
        """
        try:
            # Extract JSON from response (may have markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            # Clean up common JSON issues
            # Remove trailing commas before } or ]
            import re
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # Try to fix incomplete JSON
            # If it ends mid-object, try to close it
            if json_str.count('{') > json_str.count('}'):
                missing_closes = json_str.count('{') - json_str.count('}')
                json_str += '}' * missing_closes
            if json_str.count('[') > json_str.count(']'):
                missing_closes = json_str.count('[') - json_str.count(']')
                json_str += ']' * missing_closes

            parsed = json.loads(json_str)

            options = []
            for idx, option_data in enumerate(parsed, start=1):
                # Parse actions
                actions = []
                actions_data = option_data.get('actions', [])

                # Handle case where actions might not be a list
                if not isinstance(actions_data, list):
                    logger.warning(f"Actions is not a list for option {idx}, skipping")
                    continue

                for action_data in actions_data:
                    if not isinstance(action_data, dict):
                        logger.warning(f"Action data is not a dict, skipping: {action_data}")
                        continue

                    try:
                        action = SingleAction(
                            action_type=ActionType(action_data.get('type', 'wait')),
                            description=action_data.get('description', 'No description'),
                            is_private=action_data.get('is_private', False),
                            target_character_id=action_data.get('target'),
                            metadata=action_data
                        )
                        actions.append(action)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Error parsing action: {e}, skipping")
                        continue

                if not actions:
                    # Skip options with no valid actions
                    continue

                # Create sequence
                sequence = ActionSequence(
                    actions=actions,
                    summary=option_data.get('summary', f'Option {idx}'),
                    escalates_mood=option_data.get('escalates_mood', False),
                    deescalates_mood=option_data.get('deescalates_mood', False),
                    emotional_tone=option_data.get('emotional_tone', 'neutral'),
                    estimated_mood_impact=option_data.get('estimated_mood_impact', {}),
                    turn_duration=option_data.get('turn_duration', 1)
                )

                # Create option
                option = ActionOption(
                    option_id=idx,
                    sequence=sequence,
                    selection_weight=1.0
                )

                options.append(option)

            if options:
                return options
            else:
                # No valid options parsed, raise to trigger fallback
                raise ValueError("No valid action options parsed from response")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.error(f"Response snippet: {response[:500]}...")
            logger.error(f"JSON string attempted: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
            raise
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            logger.debug(f"Response was: {response[:1000]}...")
            raise

    def _create_fallback_deescalation(
        self,
        character: Dict[str, Any],
        location: Dict[str, Any]
    ) -> ActionOption:
        """Create a fallback de-escalation option."""
        sequence = ActionSequence(
            actions=[
                SingleAction(
                    action_type=ActionType.THINK,
                    description=f"{character['name']} thinks about calming the situation",
                    is_private=True
                ),
                SingleAction(
                    action_type=ActionType.EMOTE,
                    description=f"{character['name']} takes a deep breath and relaxes their posture",
                    is_private=False
                ),
                SingleAction(
                    action_type=ActionType.SPEAK,
                    description=f"{character['name']} says calmly, \"Let's all take a moment.\"",
                    is_private=False
                )
            ],
            summary="Attempt to calm the situation",
            escalates_mood=False,
            deescalates_mood=True,
            emotional_tone="calming",
            estimated_mood_impact={'tension': -10, 'hostility': -5}
        )

        return ActionOption(option_id=99, sequence=sequence, selection_weight=1.0)

    def _create_fallback_options(
        self,
        character: Dict[str, Any],
        location: Dict[str, Any],
        current_turn: int,
        context: Dict[str, Any]
    ) -> GeneratedActionOptions:
        """Create fallback options when generation fails."""
        logger.warning("Using fallback action options")

        options = [
            ActionOption(
                option_id=1,
                sequence=ActionSequence(
                    actions=[SingleAction(ActionType.WAIT, "Wait and observe", False)],
                    summary="Wait and observe",
                    escalates_mood=False,
                    deescalates_mood=False,
                    emotional_tone="cautious"
                )
            ),
            ActionOption(
                option_id=2,
                sequence=ActionSequence(
                    actions=[SingleAction(ActionType.SPEAK, "Speak calmly", False)],
                    summary="Speak calmly",
                    escalates_mood=False,
                    deescalates_mood=True,
                    emotional_tone="friendly"
                )
            )
        ]

        return GeneratedActionOptions(
            character_id=str(character.get('character_id')),
            turn_number=current_turn,
            options=options,
            mood_category='neutral',  # Fallback mood string
            generation_context=context
        )


class ActionSelector:
    """
    Handles selection of action options (AI random selection or player choice).
    """

    @staticmethod
    def random_select_for_ai(generated_options: GeneratedActionOptions) -> ActionOption:
        """
        Randomly select an action option for an AI character.

        Uses selection weights to bias towards certain options.

        Args:
            generated_options: Generated action options

        Returns:
            Selected action option
        """
        options = generated_options.options
        weights = [opt.selection_weight for opt in options]

        selected = random.choices(options, weights=weights, k=1)[0]

        logger.info(
            f"AI selected option {selected.option_id}: {selected.sequence.summary} "
            f"(tone: {selected.sequence.emotional_tone})"
        )

        return selected

    @staticmethod
    def player_select(
        generated_options: GeneratedActionOptions,
        choice: int
    ) -> Optional[ActionOption]:
        """
        Handle player selection of an action option.

        Args:
            generated_options: Generated action options
            choice: Option ID chosen by player (1-based)

        Returns:
            Selected action option or None if invalid choice
        """
        selected = generated_options.get_option_by_id(choice)

        if selected:
            logger.info(
                f"Player selected option {selected.option_id}: {selected.sequence.summary}"
            )
        else:
            logger.warning(f"Invalid player choice: {choice}")

        return selected
