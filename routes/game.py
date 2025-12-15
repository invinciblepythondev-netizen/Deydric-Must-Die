"""
Game routes for Deydric Must Die.

Handles the main game interface, character actions, and turn progression.
"""

from flask import Blueprint, render_template, request, jsonify, session
from sqlalchemy import text
from database import db
from services.llm_service import get_unified_llm_service
import json
from uuid import uuid4, UUID
import logging

logger = logging.getLogger(__name__)
game_bp = Blueprint('game', __name__, url_prefix='/game')

# Initialize item system (lazy initialization)
_item_parser = None
_item_generator = None
_item_store = None
_item_context_helper = None

def get_item_parser():
    """Get or initialize ItemActionParser."""
    global _item_parser
    if _item_parser is None:
        try:
            from services.item_store import ItemStore
            from services.item_action_parser import ItemActionParser
            item_store = ItemStore()
            _item_parser = ItemActionParser(item_store)
            logger.info("✓ ItemActionParser initialized")
        except Exception as e:
            logger.warning(f"Could not initialize ItemActionParser: {e}")
            _item_parser = False  # Mark as failed
    return _item_parser if _item_parser is not False else None

def get_item_generator():
    """Get or initialize ItemGenerator."""
    global _item_generator
    if _item_generator is None:
        try:
            from services.item_generator import ItemGenerator
            from services.llm_service import get_unified_llm_service
            llm_service = get_unified_llm_service()
            resilient_generator = llm_service.factory.get_action_generator()
            _item_generator = ItemGenerator(resilient_generator)
            logger.info("✓ ItemGenerator initialized")
        except Exception as e:
            logger.warning(f"Could not initialize ItemGenerator: {e}")
            _item_generator = False

def get_item_store():
    """Get or initialize ItemStore."""
    global _item_store
    if _item_store is None:
        try:
            from services.item_store import ItemStore
            _item_store = ItemStore()
            logger.info("✓ ItemStore initialized")
        except Exception as e:
            logger.warning(f"Could not initialize ItemStore: {e}")
            _item_store = False
    return _item_store if _item_store is not False else None

def get_item_context_helper():
    """Get or initialize ItemContextHelper."""
    global _item_context_helper
    if _item_context_helper is None:
        try:
            from services.item_context_helper import ItemContextHelper
            item_store = get_item_store()
            if item_store:
                _item_context_helper = ItemContextHelper(item_store)
                logger.info("✓ ItemContextHelper initialized")
            else:
                _item_context_helper = False
        except Exception as e:
            logger.warning(f"Could not initialize ItemContextHelper: {e}")
            _item_context_helper = False
    return _item_context_helper if _item_context_helper is not False else None

def process_item_changes(action_description, character_id, location_id, current_turn):
    """
    Parse action description and apply item state changes.

    Also handles lazy container generation if a container is opened,
    and generates hidden items if a search action is performed.

    Args:
        action_description: Text description of the action
        character_id: Character who performed the action
        location_id: Location where action took place
        current_turn: Current turn number

    Returns:
        List of applied item changes
    """
    item_parser = get_item_parser()
    if not item_parser:
        return []

    try:
        # Parse and apply item changes
        applied_changes = item_parser.parse_and_apply(
            action_outcome=action_description,
            character_id=UUID(character_id) if isinstance(character_id, str) else character_id,
            location_id=location_id,
            current_turn=current_turn
        )

        if applied_changes:
            logger.info(f"Applied {len(applied_changes)} item changes for turn {current_turn}")

            # Check if any containers need content generation (lazy generation)
            for change in applied_changes:
                if change.get('needs_contents_generation'):
                    generate_container_contents(
                        container_id=change['item_id'],
                        location_id=location_id,
                        current_turn=current_turn
                    )

                # Check if search action requires generating hidden items
                if change.get('needs_searchable_items_generation'):
                    generate_searchable_items(
                        location_id=change['location_id'],
                        current_turn=current_turn
                    )

        return applied_changes

    except Exception as e:
        logger.error(f"Error processing item changes: {e}")
        import traceback
        traceback.print_exc()
        return []

def generate_container_contents(container_id, location_id, current_turn):
    """
    Generate contents for a container that was just opened (lazy generation).

    Args:
        container_id: UUID of container (as string)
        location_id: Location ID
        current_turn: Current turn number
    """
    item_generator = get_item_generator()
    if not item_generator:
        logger.warning("Cannot generate container contents: ItemGenerator unavailable")
        return

    try:
        from services.item_store import ItemStore
        item_store = ItemStore()

        container = item_store.get_item(UUID(container_id))
        if not container:
            logger.error(f"Container {container_id} not found")
            return

        # Get location info for context
        location = db.session.execute(
            text("SELECT * FROM location_get(:id)"),
            {"id": location_id}
        ).fetchone()

        if not location:
            logger.error(f"Location {location_id} not found")
            return

        logger.info(f"Generating contents for container: {container['item_name']}")

        # Generate contents
        contents = item_generator.generate_container_contents(
            container_name=container['item_name'],
            container_description=container['item_description'],
            container_capacity=container['capacity'],
            location_name=location.name,
            location_description=location.description,
            container_id=UUID(container_id),
            max_items=10,
            created_turn=current_turn
        )

        # Store contents
        for item_data in contents:
            item_store.add_item(**item_data)

        # Mark container as generated
        item_store.update_item(UUID(container_id), contents_generated=True)

        logger.info(f"✓ Generated {len(contents)} items in {container['item_name']}")

    except Exception as e:
        logger.error(f"Error generating container contents: {e}")
        import traceback
        traceback.print_exc()

def generate_searchable_items(location_id, current_turn):
    """
    Generate hidden/searchable items for a location when a search action is performed.

    Args:
        location_id: Location ID where search is happening
        current_turn: Current turn number
    """
    item_generator = get_item_generator()
    if not item_generator:
        logger.warning("Cannot generate searchable items: ItemGenerator unavailable")
        return

    try:
        from services.item_store import ItemStore
        item_store = ItemStore()

        # Check if searchable items have already been generated for this location
        # by looking for hidden items at this location
        existing_hidden = item_store.search_items(
            location_id=location_id,
            visibility_levels=["hidden"],
            limit=1
        )

        if existing_hidden:
            logger.info(f"Searchable items already generated for location {location_id}, skipping")
            # Make hidden items visible (they've been found!)
            all_hidden = item_store.search_items(
                location_id=location_id,
                visibility_levels=["hidden"]
            )
            for item in all_hidden:
                item_store.update_item(
                    UUID(item['item_id']),
                    visibility_level='visible'
                )
            logger.info(f"✓ Made {len(all_hidden)} hidden items visible")
            return

        # Get location info for context
        location = db.session.execute(
            text("SELECT * FROM location_get(:id)"),
            {"id": location_id}
        ).fetchone()

        if not location:
            logger.error(f"Location {location_id} not found")
            return

        logger.info(f"Generating searchable items for location: {location.name}")

        # Generate hidden items
        searchable_items = item_generator.generate_searchable_items(
            location_name=location.name,
            location_description=location.description,
            location_id=location_id,
            max_items=5,
            created_turn=current_turn
        )

        # Store searchable items
        for item_data in searchable_items:
            item_store.add_item(**item_data)

        logger.info(f"✓ Generated {len(searchable_items)} searchable items in {location.name}")

    except Exception as e:
        logger.error(f"Error generating searchable items: {e}")
        import traceback
        traceback.print_exc()


def generate_atmospheric_description(character_name, action_description, location_name, location_description, other_characters, recent_history, current_stance=None, current_clothing=None):
    """
    Generate rich atmospheric description for an action.

    Uses resilient generator with automatic fallback for adult content
    (violence, sexual themes, disturbing content).
    """
    try:
        from services.llm.resilient_generator import AllProvidersFailedError

        # Get the resilient action generator (handles fallback for adult content)
        llm_service = get_unified_llm_service()
        resilient_generator = llm_service.factory.get_action_generator()

        # Use the resilient generator's atmospheric description method
        # This automatically classifies content intensity and uses appropriate provider chain
        result = resilient_generator.generate_atmospheric_description(
            character_name=character_name,
            action_description=action_description,
            location_name=location_name,
            location_description=location_description,
            other_characters=other_characters,
            recent_history=recent_history,
            current_stance=current_stance,
            current_clothing=current_clothing
        )

        logger.info(f"Atmospheric description generated: {len(result)} chars")
        return result

    except AllProvidersFailedError as e:
        logger.error(f"All providers failed for atmospheric description: {e}")
        # Return empty string on complete failure
        return ""
    except Exception as e:
        logger.error(f"Error generating atmospheric description: {e}")
        import traceback
        traceback.print_exc()
        return ""


def create_memory_summary(game_id, current_turn):
    """
    Create tiered memory summaries for all characters.

    Generates summaries at multiple time windows (10, 50, 100, 720 turns, etc.)
    with both descriptive (for large models) and condensed (for small models) versions.

    Uses resilient generator with automatic fallback for adult content.
    """
    from services.llm_service import get_unified_llm_service
    from services.memory_summarizer import MemorySummarizer

    try:
        logger.info(f"[Memory Summary] Starting summary generation for turn {current_turn}")

        # Get LLM provider for summarization
        llm_service = get_unified_llm_service()
        llm_provider = llm_service.factory.get_action_generator()

        # Initialize vector store for embedding summaries
        from services.vector_store import VectorStoreService
        try:
            vector_store = VectorStoreService(collection_name="game_memories")
            logger.info("✓ Vector store initialized for summary embeddings")
        except Exception as e:
            logger.warning(f"Could not initialize vector store: {e}. Summaries will not be embedded.")
            vector_store = None

        # Initialize summarizer with vector store
        summarizer = MemorySummarizer(llm_provider, vector_store=vector_store)

        # Get all characters in the game
        characters = db.session.execute(
            text("""
                SELECT DISTINCT character_id, name
                FROM character.character
                WHERE character_id IN (
                    SELECT DISTINCT character_id
                    FROM memory.turn_history
                    WHERE game_state_id = :game_id
                )
            """),
            {"game_id": str(game_id)}
        ).fetchall()

        if not characters:
            logger.warning("No characters found for summary generation")
            return

        logger.info(f"[Memory Summary] Generating summaries for {len(characters)} characters")

        # Generate summaries for each character
        total_generated = 0
        for char_id, char_name in characters:
            try:
                results = summarizer.generate_summaries_for_character(
                    db_session=db.session,
                    game_state_id=game_id,
                    character_id=char_id,
                    current_turn=current_turn
                )

                generated_count = len(results['generated'])
                total_generated += generated_count

                if generated_count > 0:
                    logger.info(f"[Memory Summary] {char_name}: Generated {generated_count} summaries")
                    for summary_info in results['generated']:
                        logger.info(
                            f"  - {summary_info['window_type']}: {summary_info['turn_range']} "
                            f"(desc: {summary_info['descriptive_len']}ch, cond: {summary_info['condensed_len']}ch)"
                        )

                if results['errors']:
                    for error in results['errors']:
                        logger.error(f"  - Error in {error['window_type']}: {error['error']}")

            except Exception as e:
                logger.error(f"[Memory Summary] Error generating summaries for {char_name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue with next character

        logger.info(f"[Memory Summary] Complete! Generated {total_generated} total summaries for {len(characters)} characters")

    except Exception as e:
        logger.error(f"[Memory Summary] Fatal error in summary generation: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - let the game continue without summary


@game_bp.route('/')
def index():
    """Main game interface."""
    try:
        # Get active game
        game = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
        ).fetchone()

        if not game:
            return render_template('game/no_game.html'), 404

        game_id = game[0]
        current_turn = game[1]

        # Get player character
        player_char = db.session.execute(
            text("""
                SELECT character_id, name, current_location_id
                FROM character.character
                WHERE is_player = TRUE
                LIMIT 1
            """)
        ).fetchone()

        if not player_char:
            return render_template('game/no_player.html'), 404

        player_id = player_char[0]
        player_name = player_char[1]
        location_id = player_char[2]

        # Get location details
        location = db.session.execute(
            text("SELECT name, description FROM world.location WHERE location_id = :loc_id"),
            {"loc_id": location_id}
        ).fetchone()

        # Get other characters in the same location with their images
        other_characters_raw = db.session.execute(
            text("""
                SELECT
                    c.character_id,
                    c.name,
                    c.current_stance,
                    c.physical_appearance,
                    c.current_clothing,
                    ci.image_url
                FROM character.character c
                LEFT JOIN character.character_image ci
                    ON c.character_id = ci.character_id
                    AND ci.image_type = 'profile'
                    AND ci.is_primary = TRUE
                WHERE c.current_location_id = :loc_id
                AND c.character_id != :player_id
            """),
            {"loc_id": location_id, "player_id": str(player_id)}
        ).fetchall()

        # Get recent turn history (last 20 entries)
        history = db.session.execute(
            text("""
                SELECT
                    th.turn_number,
                    th.sequence_number,
                    c.name as character_name,
                    th.action_type,
                    th.action_description,
                    th.is_private,
                    th.witnesses,
                    th.character_id
                FROM memory.turn_history th
                JOIN character.character c ON th.character_id = c.character_id
                WHERE th.game_state_id = :game_id
                ORDER BY th.turn_number DESC, th.sequence_number DESC
                LIMIT 30
            """),
            {"game_id": str(game_id)}
        ).fetchall()

        # Filter history - show what the player can see (all action types for now)
        visible_history = []
        for h in reversed(history):  # Reverse to chronological order
            is_private = h[5]
            witnesses = h[6] if h[6] else []
            action_char_id = str(h[7])
            action_type = h[3]

            # Player can see:
            # 1. Their own actions (including private thoughts)
            # 2. Public actions they witnessed (they're in the witnesses list)
            # 3. Atmospheric descriptions are always public
            is_players_action = (action_char_id == str(player_id))
            is_witnessed = str(player_id) in [str(w) for w in witnesses] if witnesses else False
            is_atmospheric = (action_type == 'atmospheric')

            if is_atmospheric or is_players_action or (not is_private and is_witnessed):
                # Show all action types including dialogue (think, action, speak, etc.)
                visible_history.append({
                    'turn_number': h[0],
                    'sequence_number': h[1],
                    'character_name': h[2],  # Keep character name even for atmospheric (for grouping)
                    'action_type': action_type,
                    'action_description': h[4],
                    'is_private': is_private and not is_players_action,  # Show as private only if it's not the player's
                    'is_atmospheric': is_atmospheric
                })

        # Group history by turn and character
        from collections import defaultdict
        grouped_history = defaultdict(list)
        for event in visible_history:
            key = (event['turn_number'], event['character_name'])
            grouped_history[key].append(event)

        # Sort each group by sequence_number and convert to list of grouped events
        history_groups = []
        for (turn_number, character_name), events in sorted(grouped_history.items()):
            sorted_events = sorted(events, key=lambda e: e['sequence_number'])
            history_groups.append({
                'turn_number': turn_number,
                'character_name': character_name,
                'events': sorted_events,
                'is_private': sorted_events[0]['is_private'] if sorted_events else False,
                'is_atmospheric': sorted_events[0]['is_atmospheric'] if sorted_events else False
            })

        return render_template(
            'game/play.html',
            game_id=str(game_id),
            current_turn=current_turn,
            player_id=str(player_id),
            player_name=player_name,
            location_name=location[0] if location else "Unknown",
            location_description=location[1] if location else "",
            other_characters=[
                {
                    'character_id': str(c[0]),
                    'name': c[1],
                    'stance': c[2] or 'standing',
                    'appearance': c[3],
                    'clothing': c[4],
                    'image_url': c[5]
                }
                for c in other_characters_raw
            ],
            history=history_groups
        )

    except Exception as e:
        return render_template('game/error.html', error=str(e)), 500


@game_bp.route('/actions', methods=['GET'])
def get_actions():
    """
    Generate action options for the player character.

    Uses ActionGenerator with mood tracking and intensity escalation.
    Actions will become more intense/escalated as the scene mood builds.
    """
    try:
        # Get player character with full profile
        player_char = db.session.execute(
            text("""
                SELECT
                    character_id, name, personality_traits,
                    current_emotional_state, motivations_short_term,
                    current_location_id, current_stance, current_clothing,
                    physical_appearance
                FROM character.character
                WHERE is_player = TRUE
                LIMIT 1
            """)
        ).fetchone()

        if not player_char:
            return jsonify({'error': 'No player character found'}), 404

        player_id = player_char[0]
        location_id = player_char[5]

        # Get game state
        game = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
        ).fetchone()

        if not game:
            return jsonify({'error': 'No active game found'}), 404

        game_id = game[0]
        current_turn = game[1]

        # Get location info
        location = db.session.execute(
            text("SELECT location_id, name, description FROM world.location WHERE location_id = :loc_id"),
            {"loc_id": location_id}
        ).fetchone()

        # Get other characters in location (full details for ActionGenerator)
        others = db.session.execute(
            text("""
                SELECT
                    character_id, name, physical_appearance,
                    current_stance, current_clothing
                FROM character.character
                WHERE current_location_id = :loc_id
                AND character_id != :player_id
            """),
            {"loc_id": location_id, "player_id": str(player_id)}
        ).fetchall()

        # Build character dict
        character = {
            "character_id": str(player_id),
            "name": player_char[1],
            "personality_traits": player_char[2] or [],
            "current_emotional_state": player_char[3] or "neutral",
            "motivations_short_term": player_char[4] or [],
            "current_stance": player_char[6] or "standing",
            "current_clothing": player_char[7] or "simple clothing",
            "physical_appearance": player_char[8] or ""
        }

        # Build location dict
        location_dict = {
            "location_id": str(location[0]),
            "name": location[1],
            "description": location[2]
        }

        # Build visible characters list
        visible_characters = []
        for other in others:
            visible_characters.append({
                "character_id": str(other[0]),
                "name": other[1],
                "physical_appearance": other[2],
                "current_stance": other[3],
                "current_clothing": other[4]
            })

        # Use ActionGenerator with mood tracking and intensity escalation
        from services.action_generator import ActionGenerator
        from services.llm_service import get_unified_llm_service

        llm_service = get_unified_llm_service()
        resilient_generator = llm_service.factory.get_action_generator()

        action_gen = ActionGenerator(llm_provider=resilient_generator)

        # Generate actions with mood awareness
        # This will include escalation options if mood is building
        generated_options = action_gen.generate_options(
            db_session=db.session,
            character=character,
            game_state_id=game_id,
            location=location_dict,
            visible_characters=visible_characters,
            current_turn=current_turn,
            num_options=5
        )

        # Parse actions for frontend - preserve full action sequences
        parsed_actions = []
        for option in generated_options.options:
            # Send full action sequence without combining
            action_sequence = []
            for action in option.sequence.actions:
                action_sequence.append({
                    'type': action.action_type.value,
                    'description': action.description,
                    'is_private': action.is_private
                })

            parsed_actions.append({
                'option_id': option.option_id,
                'summary': option.sequence.summary,
                'emotional_tone': option.sequence.emotional_tone,
                'actions': action_sequence,  # Full sequence array
                'escalates': option.sequence.escalates_mood,
                'deescalates': option.sequence.deescalates_mood,
                'turn_duration': option.sequence.turn_duration,
                'current_stance': option.sequence.current_stance,
                'current_clothing': option.sequence.current_clothing
            })

        return jsonify({
            'actions': parsed_actions,
            'mood_category': generated_options.mood_category  # Already a string
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error generating actions: {e}")
        return jsonify({'error': str(e)}), 500


@game_bp.route('/action', methods=['POST'])
def take_action():
    """Execute a player action."""
    try:
        data = request.get_json()
        print(f"\n📥 RECEIVED PLAYER ACTION DATA:")
        print(f"   Raw data: {data}")

        # Get action sequence array (new format) or fallback to old format
        actions = data.get('actions', [])
        emotional_tone = data.get('emotional_tone', 'neutral')
        current_stance = data.get('current_stance', 'standing')
        current_clothing = data.get('current_clothing', 'unchanged')
        turn_duration = data.get('turn_duration', 1)

        # Fallback to old format if actions array not provided
        if not actions:
            actions = []
            if data.get('thought'):
                actions.append({'type': 'think', 'description': data['thought'], 'is_private': True})
            if data.get('dialogue'):
                actions.append({'type': 'speak', 'description': data['dialogue'], 'is_private': False})
            if data.get('action'):
                actions.append({'type': 'action', 'description': data['action'], 'is_private': False})

        print(f"   Extracted values:")
        print(f"      actions: {len(actions)} actions in sequence")
        print(f"      emotional_tone: {emotional_tone}")
        print(f"      current_stance: {current_stance}")
        print(f"      current_clothing: {current_clothing}")
        print(f"      turn_duration: {turn_duration}")

        # Get game and player info
        game = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
        ).fetchone()

        player_char = db.session.execute(
            text("""
                SELECT character_id, current_location_id, name
                FROM character.character
                WHERE is_player = TRUE
                LIMIT 1
            """)
        ).fetchone()

        if not game or not player_char:
            return jsonify({'error': 'Game or player not found'}), 404

        game_id = game[0]
        current_turn = game[1]
        player_id = player_char[0]
        location_id = player_char[1]
        player_name = player_char[2]

        # Update character state (emotional state, stance, clothing)
        print(f"\n🔄 PLAYER CHARACTER STATE UPDATE:")
        print(f"   Character ID: {player_id}")
        print(f"   Emotional Tone: {emotional_tone}")
        print(f"   Current Stance: {current_stance}")
        print(f"   Current Clothing: {current_clothing}")
        print(f"   Turn Duration: {turn_duration}")

        if emotional_tone or current_stance != 'standing' or current_clothing != 'unchanged':
            print(f"   ✅ Calling character_update_state()...")
            result = db.session.execute(
                text("SELECT character_update_state(:char_id, :emotional, :stance, :clothing)"),
                {
                    "char_id": str(player_id),
                    "emotional": emotional_tone if emotional_tone else None,
                    "stance": current_stance if current_stance != 'unchanged' else None,
                    "clothing": current_clothing if current_clothing != 'unchanged' else None
                }
            )
            print(f"   ✅ character_update_state() called, result: {result.fetchone()}")

            # Verify the update
            verify = db.session.execute(
                text("""
                    SELECT name, current_emotional_state, current_stance, current_clothing
                    FROM character.character
                    WHERE character_id = :char_id
                """),
                {"char_id": str(player_id)}
            ).fetchone()
            print(f"   📊 Verification - Character state after update:")
            print(f"      Name: {verify[0]}")
            print(f"      Emotional State: {verify[1]}")
            print(f"      Stance: {verify[2]}")
            print(f"      Clothing: {verify[3]}")
        else:
            print(f"   ⚠️ Skipping update - all values are defaults")

        # Calculate remaining duration (turn_duration - 1 since we're completing first turn)
        remaining_duration = max(0, turn_duration - 1)
        print(f"   Remaining Duration: {remaining_duration}\n")

        # Get other characters in location (potential witnesses)
        others = db.session.execute(
            text("""
                SELECT character_id
                FROM character.character
                WHERE current_location_id = :loc_id
                AND character_id != :player_id
            """),
            {"loc_id": location_id, "player_id": str(player_id)}
        ).fetchall()

        witnesses_list = [str(player_id)] + [str(o[0]) for o in others]
        witnesses_json = json.dumps(witnesses_list)

        from uuid import uuid4
        sequence = 0

        # Insert each action in the sequence with proper sequence numbers
        for action in actions:
            action_type = action.get('type', 'action')
            description = action.get('description', '')
            is_private = action.get('is_private', False)

            # Determine witnesses based on privacy
            action_witnesses = f'["{player_id}"]' if is_private else witnesses_json

            if description:  # Only insert if there's a description
                db.session.execute(
                    text("""
                        INSERT INTO memory.turn_history (
                            turn_id, game_state_id, turn_number,
                            character_id, sequence_number, action_type,
                            action_description, location_id, is_private, witnesses,
                            turn_duration, remaining_duration
                        ) VALUES (
                            :turn_id, :game_id, :turn_num,
                            :char_id, :seq, :action_type,
                            :description, :loc_id, :is_private, CAST(:witnesses AS jsonb),
                            :turn_duration, :remaining_duration
                        )
                    """),
                    {
                        "turn_id": str(uuid4()),
                        "game_id": str(game_id),
                        "turn_num": current_turn + 1,
                        "char_id": str(player_id),
                        "seq": sequence,
                        "action_type": action_type,
                        "description": description,
                        "loc_id": location_id,
                        "is_private": is_private,
                        "witnesses": action_witnesses,
                        "turn_duration": turn_duration,
                        "remaining_duration": remaining_duration
                    }
                )
                sequence += 1

                # Process item changes from this action (if any)
                if not is_private:  # Only process public actions for item manipulations
                    process_item_changes(
                        action_description=description,
                        character_id=player_id,
                        location_id=location_id,
                        current_turn=current_turn + 1
                    )

        # Generate and insert atmospheric description
        try:
            # Get player info (name, stance, clothing)
            player_info = db.session.execute(
                text("SELECT name, current_stance, current_clothing FROM character.character WHERE character_id = :id"),
                {"id": str(player_id)}
            ).fetchone()

            location = db.session.execute(
                text("SELECT name, description FROM world.location WHERE location_id = :loc_id"),
                {"loc_id": location_id}
            ).fetchone()

            # Get other character names
            others = db.session.execute(
                text("""
                    SELECT name FROM character.character
                    WHERE current_location_id = :loc_id AND character_id != :player_id
                """),
                {"loc_id": location_id, "player_id": str(player_id)}
            ).fetchall()

            other_names = [o[0] for o in others]

            # Get recent history for context
            history = db.session.execute(
                text("""
                    SELECT c.name, th.action_description
                    FROM memory.turn_history th
                    JOIN character.character c ON th.character_id = c.character_id
                    WHERE th.game_state_id = :game_id
                    ORDER BY th.turn_number DESC, th.sequence_number DESC
                    LIMIT 3
                """),
                {"game_id": str(game_id)}
            ).fetchall()

            recent_history = " ".join([f"{h[0]}: {h[1]}" for h in reversed(history)])

            # Build combined action description for atmospheric context
            combined_action = ''
            for action in actions:
                action_type = action.get('type', '')
                description = action.get('description', '')

                if action_type == 'speak' and description:
                    if combined_action:
                        combined_action += f' and says "{description}"'
                    else:
                        combined_action = f'says "{description}"'
                elif action_type != 'think' and description:  # Skip thoughts for atmospheric
                    if combined_action:
                        combined_action += f' and {description}'
                    else:
                        combined_action = description

            # Generate atmospheric description with mood analysis
            atmos_result = generate_atmospheric_description(
                character_name=player_info[0] if player_info else player_name,
                action_description=combined_action if combined_action else "acts",
                location_name=location[0] if location else "Unknown",
                location_description=location[1] if location else "",
                other_characters=other_names,
                recent_history=recent_history,
                current_stance=player_info[1] if player_info else None,
                current_clothing=player_info[2] if player_info else None
            )

            atmos_desc = atmos_result.get('description', '') if isinstance(atmos_result, dict) else atmos_result
            mood_deltas = atmos_result.get('mood_deltas', {}) if isinstance(atmos_result, dict) else {}

            # Apply item changes from atmospheric description (if any)
            if isinstance(atmos_result, dict) and atmos_result.get('item_changes'):
                item_helper = get_item_context_helper()
                if item_helper:
                    try:
                        updated_count = item_helper.apply_item_changes_from_atmospheric_description(
                            atmos_result,
                            location_id=location_id,
                            character_id=player_id
                        )
                        if updated_count > 0:
                            logger.info(f"Applied {updated_count} item changes from atmospheric description")
                    except Exception as e:
                        logger.warning(f"Failed to apply item changes: {e}")

            # Insert atmospheric description if generated
            if atmos_desc:
                db.session.execute(
                    text("""
                        INSERT INTO memory.turn_history (
                            turn_id, game_state_id, turn_number,
                            character_id, sequence_number, action_type,
                            action_description, location_id, is_private, witnesses,
                            turn_duration, remaining_duration
                        ) VALUES (
                            :turn_id, :game_id, :turn_num,
                            :char_id, :seq, 'atmospheric',
                            :desc, :loc_id, FALSE, CAST(:witnesses AS jsonb),
                            :turn_duration, :remaining_duration
                        )
                    """),
                    {
                        "turn_id": str(uuid4()),
                        "game_id": str(game_id),
                        "turn_num": current_turn + 1,
                        "char_id": str(player_id),  # Associate with player for filtering
                        "seq": sequence,  # Use the current sequence number
                        "desc": atmos_desc,
                        "loc_id": location_id,
                        "witnesses": witnesses_json,
                        "turn_duration": turn_duration,
                        "remaining_duration": remaining_duration
                    }
                )
        except Exception as e:
            logger.error(f"Error generating atmospheric description: {e}")
            # Continue even if atmospheric description fails

        # Increment turn
        db.session.execute(
            text("""
                UPDATE game.game_state
                SET current_turn = current_turn + 1
                WHERE game_state_id = :game_id
            """),
            {"game_id": str(game_id)}
        )

        # Commit the turn to save all actions and character state updates
        print(f"\n💾 Committing transaction...")
        db.session.commit()
        print(f"✅ Transaction committed successfully!\n")

        # Update scene mood based on LLM-analyzed mood deltas (after commit to avoid transaction abort)
        try:
            from models.scene_mood import SceneMood

            # Get mood deltas from LLM-generated atmospheric analysis
            tension_delta = mood_deltas.get('tension', 0) if 'mood_deltas' in locals() else 0
            romance_delta = mood_deltas.get('romance', 0) if 'mood_deltas' in locals() else 0
            hostility_delta = mood_deltas.get('hostility', 0) if 'mood_deltas' in locals() else 0
            cooperation_delta = mood_deltas.get('cooperation', 0) if 'mood_deltas' in locals() else 0

            # Apply mood adjustments if any changes detected
            if any([tension_delta, romance_delta, hostility_delta, cooperation_delta]):
                # Check if mood exists, create if not
                existing_mood = SceneMood.get(
                    db_session=db.session,
                    game_state_id=game_id,
                    location_id=location_id
                )

                if not existing_mood:
                    # Initialize mood for this location
                    logger.info(f"Initializing mood for location {location_id}")
                    SceneMood.create_or_update(
                        db_session=db.session,
                        game_state_id=game_id,
                        location_id=location_id,
                        tension_level=0,
                        romance_level=0,
                        hostility_level=0,
                        cooperation_level=0,
                        last_mood_change_turn=current_turn + 1
                    )
                    # create_or_update commits internally, so we're good

                # Now adjust the mood based on LLM analysis
                SceneMood.adjust(
                    db_session=db.session,
                    game_state_id=game_id,
                    location_id=location_id,
                    tension_delta=tension_delta,
                    romance_delta=romance_delta,
                    hostility_delta=hostility_delta,
                    cooperation_delta=cooperation_delta,
                    current_turn=current_turn + 1,
                    mood_change_description=f"{player_name}: {combined_action if combined_action else 'acts'}"
                )
                logger.info(
                    f"Mood adjusted (LLM-analyzed): tension={tension_delta:+d}, romance={romance_delta:+d}, "
                    f"hostility={hostility_delta:+d}, cooperation={cooperation_delta:+d}"
                )

        except Exception as e:
            logger.error(f"Error adjusting mood: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the turn if mood adjustment fails

        # Build action_data for response (for frontend history display)
        action_data = {
            'turn_number': current_turn + 1,
            'character_name': player_name,
            'actions': actions,
            'atmospheric': atmos_desc if 'atmos_desc' in locals() else ''
        }

        # Add legacy fields for backwards compatibility
        for action in actions:
            if action.get('type') == 'think':
                action_data.setdefault('thought', action.get('description', ''))
            elif action.get('type') == 'speak':
                action_data.setdefault('dialogue', action.get('description', ''))
            elif action.get('type') in ['action', 'interact']:
                action_data.setdefault('action', action.get('description', ''))

        return jsonify({
            'success': True,
            'turn': current_turn + 1,
            'action_data': action_data
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@game_bp.route('/ai-turn', methods=['POST'])
def ai_turn():
    """Execute AI character turn."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get game info
        game = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
        ).fetchone()

        if not game:
            return jsonify({'error': 'No active game'}), 404

        game_id = game[0]
        current_turn = game[1]

        # Get player's location first
        player = db.session.execute(
            text("SELECT character_id, current_location_id FROM character.character WHERE is_player = TRUE LIMIT 1")
        ).fetchone()

        if not player or player[1] is None:
            return jsonify({'error': 'Player has no location'}), 400

        player_location_id = player[1]

        # Get only AI characters in the same location as the player
        ai_chars = db.session.execute(
            text("""
                SELECT
                    character_id, name, personality_traits,
                    current_emotional_state, motivations_short_term,
                    current_location_id, current_stance, current_clothing,
                    physical_appearance
                FROM character.character
                WHERE is_player = FALSE
                AND current_location_id = :player_location_id
            """),
            {"player_location_id": player_location_id}
        ).fetchall()

        if not ai_chars:
            logger.info("No AI characters in player's location, skipping AI turn")
            db.session.execute(
                text("UPDATE game.game_state SET current_turn = current_turn + 1 WHERE game_state_id = :game_id"),
                {"game_id": str(game_id)}
            )
            db.session.commit()
            return jsonify({'success': True, 'turn': current_turn + 1, 'message': 'No AI characters present'})

        for char in ai_chars:
            char_id = char[0]
            location_id = char[5]

            # Get location info
            location = db.session.execute(
                text("SELECT location_id, name, description FROM world.location WHERE location_id = :loc_id"),
                {"loc_id": location_id}
            ).fetchone()

            # Get other characters in location (with full details for ActionGenerator)
            others = db.session.execute(
                text("""
                    SELECT
                        character_id, name, physical_appearance,
                        current_stance, current_clothing
                    FROM character.character
                    WHERE current_location_id = :loc_id
                    AND character_id != :char_id
                """),
                {"loc_id": location_id, "char_id": str(char_id)}
            ).fetchall()

            # Build character dict (with character_id for ActionGenerator)
            character = {
                "character_id": str(char_id),
                "name": char[1],
                "personality_traits": char[2] or [],
                "current_emotional_state": char[3] or "neutral",
                "motivations_short_term": char[4] or [],
                "current_stance": char[6] or "standing",
                "current_clothing": char[7] or "simple clothing",
                "physical_appearance": char[8] or ""
            }

            # Build location dict
            location_dict = {
                "location_id": location[0] if location else location_id,
                "name": location[1] if location else "Unknown",
                "description": location[2] if location else ""
            }

            # Build visible characters list
            visible_characters = []
            for other in others:
                visible_characters.append({
                    "character_id": str(other[0]),
                    "name": other[1],
                    "physical_appearance": other[2],
                    "current_stance": other[3],
                    "current_clothing": other[4]
                })

            # Use ActionGenerator with draft system and mood tracking (same as player)
            from services.action_generator import ActionGenerator, ActionSelector
            from services.llm_service import get_unified_llm_service

            llm_service = get_unified_llm_service()
            resilient_generator = llm_service.factory.get_action_generator()

            action_gen = ActionGenerator(llm_provider=resilient_generator)

            logger.info(f"Generating actions for AI character {char[1]} using ActionGenerator with draft system")
            print(f"🤖 Generating actions for AI character {char[1]} with draft system...")

            # Generate action options with mood awareness and draft selection
            generated_options = action_gen.generate_options(
                db_session=db.session,
                character=character,
                game_state_id=game_id,
                location=location_dict,
                visible_characters=visible_characters,
                current_turn=current_turn,
                num_options=5  # Generate 5 options, then AI selects one
            )

            # AI randomly selects one option from the generated options
            selected_option = ActionSelector.random_select_for_ai(generated_options)

            logger.info(f"AI character {char[1]} selected: {selected_option.sequence.summary}")
            #print(f"🤖 AI {char[1]} selected: {selected_option.sequence.summary}")
            print(f"🤖 AI {char[1]} selected: {selected_option}")

            # Extract action sequence from the selected option
            actions = []
            for action in selected_option.sequence.actions:
                actions.append({
                    'type': action.action_type.value,
                    'description': action.description,
                    'is_private': action.is_private
                })

            emotional_tone = selected_option.sequence.emotional_tone
            current_stance = selected_option.sequence.current_stance
            current_clothing = selected_option.sequence.current_clothing
            turn_duration = selected_option.sequence.turn_duration

            # Update character state (emotional state, stance, clothing)
            print(f"\n🔄 AI CHARACTER STATE UPDATE:")
            print(f"   Character: {char[1]} (ID: {char_id})")
            print(f"   Emotional Tone: {emotional_tone}")
            print(f"   Current Stance: {current_stance}")
            print(f"   Current Clothing: {current_clothing}")
            print(f"   Turn Duration: {turn_duration}")

            if emotional_tone or current_stance != 'standing' or current_clothing != 'unchanged':
                print(f"   ✅ Calling character_update_state()...")
                result = db.session.execute(
                    text("SELECT character_update_state(:char_id, :emotional, :stance, :clothing)"),
                    {
                        "char_id": str(char_id),
                        "emotional": emotional_tone if emotional_tone else None,
                        "stance": current_stance if current_stance != 'unchanged' else None,
                        "clothing": current_clothing if current_clothing != 'unchanged' else None
                    }
                )
                print(f"   ✅ character_update_state() called, result: {result.fetchone()}")

                # Verify the update
                verify = db.session.execute(
                    text("""
                        SELECT name, current_emotional_state, current_stance, current_clothing
                        FROM character.character
                        WHERE character_id = :char_id
                    """),
                    {"char_id": str(char_id)}
                ).fetchone()
                print(f"   📊 Verification - Character state after update:")
                print(f"      Name: {verify[0]}")
                print(f"      Emotional State: {verify[1]}")
                print(f"      Stance: {verify[2]}")
                print(f"      Clothing: {verify[3]}")
            else:
                print(f"   ⚠️ Skipping update - all values are defaults")

            # Calculate remaining duration (turn_duration - 1 since we're completing first turn)
            remaining_duration = max(0, turn_duration - 1)
            print(f"   Remaining Duration: {remaining_duration}\n")

            # Continue with existing logic
            if actions:
                # Get witnesses
                witnesses = db.session.execute(
                    text("""
                        SELECT character_id
                        FROM character.character
                        WHERE current_location_id = :loc_id
                    """),
                    {"loc_id": location_id}
                ).fetchall()

                witnesses_list = [str(w[0]) for w in witnesses]
                witnesses_json = json.dumps(witnesses_list)

                from uuid import uuid4
                sequence = 0

                # Insert each action in the sequence with proper sequence numbers
                for action in actions:
                    action_type = action.get('type', 'action')
                    description = action.get('description', '')
                    is_private = action.get('is_private', False)

                    # Determine witnesses based on privacy
                    action_witnesses = f'["{char_id}"]' if is_private else witnesses_json

                    if description:  # Only insert if there's a description
                        db.session.execute(
                            text("""
                                INSERT INTO memory.turn_history (
                                    turn_id, game_state_id, turn_number,
                                    character_id, sequence_number, action_type,
                                    action_description, location_id, is_private, witnesses,
                                    turn_duration, remaining_duration
                                ) VALUES (
                                    :turn_id, :game_id, :turn_num,
                                    :char_id, :seq, :action_type,
                                    :description, :loc_id, :is_private, CAST(:witnesses AS jsonb),
                                    :turn_duration, :remaining_duration
                                )
                            """),
                            {
                                "turn_id": str(uuid4()),
                                "game_id": str(game_id),
                                "turn_num": current_turn + 1,
                                "char_id": str(char_id),
                                "seq": sequence,
                                "action_type": action_type,
                                "description": description,
                                "loc_id": location_id,
                                "is_private": is_private,
                                "witnesses": action_witnesses,
                                "turn_duration": turn_duration,
                                "remaining_duration": remaining_duration
                            }
                        )
                        sequence += 1

                        # Process item changes from this action (if any)
                        if not is_private:  # Only process public actions for item manipulations
                            process_item_changes(
                                action_description=description,
                                character_id=char_id,
                                location_id=location_id,
                                current_turn=current_turn + 1
                            )

                # Generate and insert atmospheric description for AI action
                try:
                    # Get other character names
                    others_ai = db.session.execute(
                        text("""
                            SELECT name FROM character.character
                            WHERE current_location_id = :loc_id AND character_id != :char_id
                        """),
                        {"loc_id": location_id, "char_id": str(char_id)}
                    ).fetchall()

                    other_names_ai = [o[0] for o in others_ai]

                    # Get recent history
                    history_ai = db.session.execute(
                        text("""
                            SELECT c.name, th.action_description
                            FROM memory.turn_history th
                            JOIN character.character c ON th.character_id = c.character_id
                            WHERE th.game_state_id = :game_id
                            ORDER BY th.turn_number DESC, th.sequence_number DESC
                            LIMIT 3
                        """),
                        {"game_id": str(game_id)}
                    ).fetchall()

                    recent_history_ai = " ".join([f"{h[0]}: {h[1]}" for h in reversed(history_ai)])

                    # Build combined action description for atmospheric context
                    combined_action_ai = ''
                    for action in actions:
                        action_type = action.get('type', '')
                        description = action.get('description', '')

                        if action_type == 'speak' and description:
                            if combined_action_ai:
                                combined_action_ai += f' and says "{description}"'
                            else:
                                combined_action_ai = f'says "{description}"'
                        elif action_type != 'think' and description:  # Skip thoughts for atmospheric
                            if combined_action_ai:
                                combined_action_ai += f' and {description}'
                            else:
                                combined_action_ai = description

                    # Generate atmospheric description with mood analysis
                    atmos_result_ai = generate_atmospheric_description(
                        character_name=char[1],
                        action_description=combined_action_ai if combined_action_ai else "acts",
                        location_name=location[0] if location else "Unknown",
                        location_description=location[1] if location else "",
                        other_characters=other_names_ai,
                        recent_history=recent_history_ai,
                        current_stance=char[6] if len(char) > 6 else None,
                        current_clothing=char[7] if len(char) > 7 else None
                    )

                    atmos_desc_ai = atmos_result_ai.get('description', '') if isinstance(atmos_result_ai, dict) else atmos_result_ai
                    mood_deltas_ai = atmos_result_ai.get('mood_deltas', {}) if isinstance(atmos_result_ai, dict) else {}

                    # Apply item changes from atmospheric description (if any)
                    if isinstance(atmos_result_ai, dict) and atmos_result_ai.get('item_changes'):
                        item_helper = get_item_context_helper()
                        if item_helper:
                            try:
                                updated_count = item_helper.apply_item_changes_from_atmospheric_description(
                                    atmos_result_ai,
                                    location_id=location_id,
                                    character_id=char_id
                                )
                                if updated_count > 0:
                                    logger.info(f"Applied {updated_count} item changes from AI atmospheric description")
                            except Exception as e:
                                logger.warning(f"Failed to apply AI item changes: {e}")

                    # Insert atmospheric description if generated
                    if atmos_desc_ai:
                        db.session.execute(
                            text("""
                                INSERT INTO memory.turn_history (
                                    turn_id, game_state_id, turn_number,
                                    character_id, sequence_number, action_type,
                                    action_description, location_id, is_private, witnesses,
                                    turn_duration, remaining_duration
                                ) VALUES (
                                    :turn_id, :game_id, :turn_num,
                                    :char_id, :seq, 'atmospheric',
                                    :desc, :loc_id, FALSE, CAST(:witnesses AS jsonb),
                                    :turn_duration, :remaining_duration
                                )
                            """),
                            {
                                "turn_id": str(uuid4()),
                                "game_id": str(game_id),
                                "turn_num": current_turn + 1,
                                "char_id": str(char_id),
                                "seq": sequence,  # Use the current sequence number
                                "desc": atmos_desc_ai,
                                "loc_id": location_id,
                                "witnesses": witnesses_json,
                                "turn_duration": turn_duration,
                                "remaining_duration": remaining_duration
                            }
                        )
                except Exception as e:
                    logger.error(f"Error generating AI atmospheric description: {e}")
                    # Continue even if atmospheric description fails

        # Increment turn
        new_turn = current_turn + 1
        db.session.execute(
            text("""
                UPDATE game.game_state
                SET current_turn = current_turn + 1
                WHERE game_state_id = :game_id
            """),
            {"game_id": str(game_id)}
        )

        print(f"\n💾 Committing AI turn transaction...")
        db.session.commit()
        print(f"✅ AI turn transaction committed successfully!\n")

        # Update scene mood based on LLM-analyzed mood deltas (after commit to avoid transaction abort)
        try:
            from models.scene_mood import SceneMood

            # Get mood deltas from LLM-generated atmospheric analysis
            if 'mood_deltas_ai' in locals():
                tension_delta = mood_deltas_ai.get('tension', 0)
                romance_delta = mood_deltas_ai.get('romance', 0)
                hostility_delta = mood_deltas_ai.get('hostility', 0)
                cooperation_delta = mood_deltas_ai.get('cooperation', 0)

                # Apply mood adjustments if any changes detected
                if any([tension_delta, romance_delta, hostility_delta, cooperation_delta]):
                    # Check if mood exists, create if not
                    existing_mood = SceneMood.get(
                        db_session=db.session,
                        game_state_id=game_id,
                        location_id=player_location_id
                    )

                    if not existing_mood:
                        # Initialize mood for this location
                        logger.info(f"Initializing mood for location {player_location_id}")
                        SceneMood.create_or_update(
                            db_session=db.session,
                            game_state_id=game_id,
                            location_id=player_location_id,
                            tension_level=0,
                            romance_level=0,
                            hostility_level=0,
                            cooperation_level=0,
                            last_mood_change_turn=new_turn
                        )

                    # Now adjust the mood based on LLM analysis
                    SceneMood.adjust(
                        db_session=db.session,
                        game_state_id=game_id,
                        location_id=player_location_id,
                        tension_delta=tension_delta,
                        romance_delta=romance_delta,
                        hostility_delta=hostility_delta,
                        cooperation_delta=cooperation_delta,
                        current_turn=new_turn,
                        mood_change_description=f"AI character action"
                    )
                    logger.info(
                        f"AI Mood adjusted (LLM-analyzed): tension={tension_delta:+d}, romance={romance_delta:+d}, "
                        f"hostility={hostility_delta:+d}, cooperation={cooperation_delta:+d}"
                    )

        except Exception as e:
            logger.error(f"Error adjusting AI mood: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the turn if mood adjustment fails

        # Create memory summary every 10 turns
        if new_turn % 10 == 0:
            try:
                logger.info(f"Creating memory summary for turns {new_turn-9} to {new_turn}")
                create_memory_summary(game_id, new_turn)
            except Exception as e:
                logger.error(f"Failed to create memory summary: {e}")
                # Don't fail the turn if summarization fails

        return jsonify({'success': True, 'turn': new_turn})

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
