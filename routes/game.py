"""
Game routes for Deydric Must Die.

Handles the main game interface, character actions, and turn progression.
"""

from flask import Blueprint, render_template, request, jsonify, session
from sqlalchemy import text
from database import db
from services.llm_service import get_unified_llm_service
import json
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)
game_bp = Blueprint('game', __name__, url_prefix='/game')


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
    Create a memory summary for the last 10 turns.

    Uses resilient generator with automatic fallback for adult content
    (violence, sexual themes, disturbing content).
    """
    from uuid import uuid4
    from services.llm_service import get_unified_llm_service
    from services.llm.resilient_generator import AllProvidersFailedError

    try:
        # Get turns to summarize (last 10 turns)
        start_turn = max(1, current_turn - 9)
        end_turn = current_turn

        # Fetch turn history
        turns = db.session.execute(
            text("""
                SELECT
                    th.turn_number,
                    c.name as character_name,
                    th.action_type,
                    th.action_description,
                    th.sequence_number
                FROM memory.turn_history th
                JOIN character.character c ON th.character_id = c.character_id
                WHERE th.game_state_id = :game_id
                    AND th.turn_number >= :start_turn
                    AND th.turn_number <= :end_turn
                    AND th.action_type != 'atmospheric'
                ORDER BY th.turn_number ASC, th.sequence_number ASC
            """),
            {"game_id": str(game_id), "start_turn": start_turn, "end_turn": end_turn}
        ).fetchall()

        if not turns:
            logger.warning(f"No turns found for summarization (turns {start_turn}-{end_turn})")
            return

        # Format turns for summarization
        turn_data = []
        for turn in turns:
            turn_data.append({
                'turn_number': turn[0],
                'action_description': f"{turn[1]} ({turn[2]}): {turn[3]}"
            })

        # Generate summary using resilient generator (handles adult content with fallback)
        llm_service = get_unified_llm_service()
        resilient_generator = llm_service.factory.get_action_generator()

        # Use resilient generator's summarize_memory method
        # This automatically classifies content intensity and uses appropriate provider chain
        summary = resilient_generator.summarize_memory(turn_data, importance="routine")

        # Store summary in database
        summary_id = uuid4()
        db.session.execute(
            text("""
                INSERT INTO memory.memory_summary (
                    summary_id, game_state_id, start_turn, end_turn,
                    summary_text, importance, created_at
                ) VALUES (
                    :summary_id, :game_id, :start_turn, :end_turn,
                    :summary_text, :importance, NOW()
                )
            """),
            {
                "summary_id": str(summary_id),
                "game_id": str(game_id),
                "start_turn": start_turn,
                "end_turn": end_turn,
                "summary_text": summary,
                "importance": "routine"
            }
        )
        db.session.commit()

        logger.info(f"Created memory summary {summary_id} for turns {start_turn}-{end_turn}")

    except AllProvidersFailedError as e:
        logger.error(f"All providers failed for memory summarization: {e}")
        # Don't raise - let the game continue without summary
    except Exception as e:
        logger.error(f"Error creating memory summary: {e}")
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
                    'character_name': h[2] if not is_atmospheric else '',
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

        # Parse actions for frontend
        parsed_actions = []
        for option in generated_options.options:
            # Combine multi-action sequences into single display format
            thought_parts = []
            dialogue_parts = []
            action_parts = []

            for action in option.sequence.actions:
                if action.action_type.value == 'think':
                    thought_parts.append(action.description)
                elif action.action_type.value == 'speak':
                    dialogue_parts.append(action.description)
                else:
                    action_parts.append(action.description)

            parsed_actions.append({
                'option_id': option.option_id,
                'summary': option.sequence.summary,
                'emotional_tone': option.sequence.emotional_tone,
                'private_thought': ' '.join(thought_parts),
                'dialogue': ' '.join(dialogue_parts),
                'action': ' '.join(action_parts),
                'escalates': option.sequence.escalates_mood,
                'deescalates': option.sequence.deescalates_mood
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
        thought_text = data.get('thought', '')
        dialogue_text = data.get('dialogue', '')
        action_text = data.get('action', '')
        emotional_tone = data.get('emotional_tone', '')

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

        # Insert thought (private action) if provided
        if thought_text:
            db.session.execute(
                text("""
                    INSERT INTO memory.turn_history (
                        turn_id, game_state_id, turn_number,
                        character_id, sequence_number, action_type,
                        action_description, location_id, is_private, witnesses
                    ) VALUES (
                        :turn_id, :game_id, :turn_num,
                        :char_id, :seq, 'think',
                        :thought, :loc_id, TRUE, CAST(:witnesses AS jsonb)
                    )
                """),
                {
                    "turn_id": str(uuid4()),
                    "game_id": str(game_id),
                    "turn_num": current_turn + 1,
                    "char_id": str(player_id),
                    "seq": sequence,
                    "thought": thought_text,
                    "loc_id": location_id,
                    "witnesses": f'["{player_id}"]'  # Only player knows their thoughts
                }
            )
            sequence += 1

        # Insert dialogue (public) if provided
        if dialogue_text:
            db.session.execute(
                text("""
                    INSERT INTO memory.turn_history (
                        turn_id, game_state_id, turn_number,
                        character_id, sequence_number, action_type,
                        action_description, location_id, is_private, witnesses
                    ) VALUES (
                        :turn_id, :game_id, :turn_num,
                        :char_id, :seq, 'speak',
                        :dialogue, :loc_id, FALSE, CAST(:witnesses AS jsonb)
                    )
                """),
                {
                    "turn_id": str(uuid4()),
                    "game_id": str(game_id),
                    "turn_num": current_turn + 1,
                    "char_id": str(player_id),
                    "seq": sequence,
                    "dialogue": dialogue_text,
                    "loc_id": location_id,
                    "witnesses": witnesses_json
                }
            )
            sequence += 1

        # Insert physical action (public) if provided
        if action_text:
            db.session.execute(
                text("""
                    INSERT INTO memory.turn_history (
                        turn_id, game_state_id, turn_number,
                        character_id, sequence_number, action_type,
                        action_description, location_id, is_private, witnesses
                    ) VALUES (
                        :turn_id, :game_id, :turn_num,
                        :char_id, :seq, 'action',
                        :action, :loc_id, FALSE, CAST(:witnesses AS jsonb)
                    )
                """),
                {
                    "turn_id": str(uuid4()),
                    "game_id": str(game_id),
                    "turn_num": current_turn + 1,
                    "char_id": str(player_id),
                    "seq": sequence,
                    "action": action_text,
                    "loc_id": location_id,
                    "witnesses": witnesses_json
                }
            )
            sequence += 1

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
            if dialogue_text:
                combined_action = f'says "{dialogue_text}"'
            if action_text:
                if combined_action:
                    combined_action += f' and {action_text}'
                else:
                    combined_action = action_text

            # Generate atmospheric description
            atmos_desc = generate_atmospheric_description(
                character_name=player_info[0] if player_info else player_name,
                action_description=combined_action if combined_action else "acts",
                location_name=location[0] if location else "Unknown",
                location_description=location[1] if location else "",
                other_characters=other_names,
                recent_history=recent_history,
                current_stance=player_info[1] if player_info else None,
                current_clothing=player_info[2] if player_info else None
            )

            # Insert atmospheric description if generated
            if atmos_desc:
                db.session.execute(
                    text("""
                        INSERT INTO memory.turn_history (
                            turn_id, game_state_id, turn_number,
                            character_id, sequence_number, action_type,
                            action_description, location_id, is_private, witnesses
                        ) VALUES (
                            :turn_id, :game_id, :turn_num,
                            :char_id, :seq, 'atmospheric',
                            :desc, :loc_id, FALSE, CAST(:witnesses AS jsonb)
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
                        "witnesses": witnesses_json
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

        # Commit the turn first to save all actions
        db.session.commit()

        # Update character emotional state based on action's emotional tone
        if emotional_tone and emotional_tone.strip():
            try:
                # Use the emotional_tone directly as the emotional state
                db.session.execute(
                    text("""
                        UPDATE character.character
                        SET current_emotional_state = :state
                        WHERE character_id = :char_id
                    """),
                    {
                        "state": emotional_tone,
                        "char_id": str(player_id)
                    }
                )
                db.session.commit()

                logger.info(f"Updated character emotional state to: {emotional_tone}")
            except Exception as e:
                logger.error(f"Error updating character emotional state: {e}")
                # Continue even if emotional state update fails

        # Update scene mood based on action content (after commit to avoid transaction abort)
        try:
            from models.scene_mood import SceneMood

            # Analyze action content to determine mood impact
            combined_text = f"{dialogue_text} {action_text}".lower()

            tension_delta = 0
            romance_delta = 0
            hostility_delta = 0
            cooperation_delta = 0

            # Detect escalation keywords
            escalation_keywords = ['attack', 'strike', 'hit', 'punch', 'kick', 'grab', 'force', 'threaten', 'push', 'shove', 'slam', 'stab', 'cut']
            if any(keyword in combined_text for keyword in escalation_keywords):
                tension_delta += 15
                hostility_delta += 10

            # Detect violence/combat
            violence_keywords = ['blood', 'wound', 'pain', 'scream', 'cry out', 'hurt']
            if any(keyword in combined_text for keyword in violence_keywords):
                tension_delta += 10
                hostility_delta += 5

            # Detect de-escalation keywords
            deescalation_keywords = ['calm', 'relax', 'sorry', 'apologize', 'step back', 'back away', 'surrender', 'yield', 'peace']
            if any(keyword in combined_text for keyword in deescalation_keywords):
                tension_delta -= 10
                hostility_delta -= 5
                cooperation_delta += 5

            # Detect romantic/intimate actions
            romance_keywords = ['kiss', 'embrace', 'caress', 'touch gently', 'stroke', 'hold close', 'whisper', 'love', 'desire']
            if any(keyword in combined_text for keyword in romance_keywords):
                romance_delta += 10
                tension_delta += 5  # Romantic tension

            # Detect sexual content (builds romantic/sexual tension)
            sexual_keywords = ['undress', 'clothes off', 'naked', 'bare skin', 'lips on', 'body against', 'desire', 'lust', 'pleasure', 'moan', 'pant', 'thrust', 'penetrate', 'orgasm', 'sex', 'rub', 'nipple', 'breast', 'genital', 'intimate', 'erotic', 'cock', 'pussy']
            if any(keyword in combined_text for keyword in sexual_keywords):
                romance_delta += 15
                tension_delta += 10

            # Detect hostile speech
            hostile_keywords = ['you bastard', 'you fool', 'idiot', 'hate', 'despise', 'curse', 'damn you', 'fool']
            if any(keyword in combined_text for keyword in hostile_keywords):
                hostility_delta += 8
                tension_delta += 5

            # Detect friendly/cooperative actions
            friendly_keywords = ['help', 'assist', 'thank', 'appreciate', 'agree', 'smile', 'nod', 'together']
            if any(keyword in combined_text for keyword in friendly_keywords):
                cooperation_delta += 5
                hostility_delta -= 3

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

                # Now adjust the mood
                SceneMood.adjust(
                    db_session=db.session,
                    game_state_id=game_id,
                    location_id=location_id,
                    tension_delta=tension_delta,
                    romance_delta=romance_delta,
                    hostility_delta=hostility_delta,
                    cooperation_delta=cooperation_delta,
                    current_turn=current_turn + 1,
                    mood_change_description=f"{player_name}: {action_text}"
                )
                logger.info(
                    f"Mood adjusted: tension={tension_delta:+d}, romance={romance_delta:+d}, "
                    f"hostility={hostility_delta:+d}, cooperation={cooperation_delta:+d}"
                )

        except Exception as e:
            logger.error(f"Error adjusting mood: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the turn if mood adjustment fails

        return jsonify({'success': True, 'turn': current_turn + 1})

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

        # Store emotional tones for each character to update after commit
        char_emotional_tones = {}

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
            print(f"🤖 AI {char[1]} selected: {selected_option.sequence.summary}")

            # Extract actions from the selected option
            thought = ''
            dialogue = ''
            physical_action = ''
            emotional_tone = selected_option.sequence.emotional_tone

            for action in selected_option.sequence.actions:
                if action.action_type.value == 'think':
                    thought = action.description
                elif action.action_type.value == 'speak':
                    dialogue = action.description
                else:
                    physical_action = action.description

            # Continue with existing logic
            if thought or dialogue or physical_action:

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

                # Record thought if present
                if thought:
                    db.session.execute(
                        text("""
                            INSERT INTO memory.turn_history (
                                turn_id, game_state_id, turn_number,
                                character_id, sequence_number, action_type,
                                action_description, location_id, is_private, witnesses
                            ) VALUES (
                                :turn_id, :game_id, :turn_num,
                                :char_id, :seq, 'think',
                                :thought, :loc_id, TRUE, CAST(:witnesses AS jsonb)
                            )
                        """),
                        {
                            "turn_id": str(uuid4()),
                            "game_id": str(game_id),
                            "turn_num": current_turn + 1,
                            "char_id": str(char_id),
                            "seq": sequence,
                            "thought": thought,
                            "loc_id": location_id,
                            "witnesses": f'["{char_id}"]'
                        }
                    )
                    sequence += 1

                # Record dialogue if present
                if dialogue:
                    db.session.execute(
                        text("""
                            INSERT INTO memory.turn_history (
                                turn_id, game_state_id, turn_number,
                                character_id, sequence_number, action_type,
                                action_description, location_id, is_private, witnesses
                            ) VALUES (
                                :turn_id, :game_id, :turn_num,
                                :char_id, :seq, 'speak',
                                :dialogue, :loc_id, FALSE, CAST(:witnesses AS jsonb)
                            )
                        """),
                        {
                            "turn_id": str(uuid4()),
                            "game_id": str(game_id),
                            "turn_num": current_turn + 1,
                            "char_id": str(char_id),
                            "seq": sequence,
                            "dialogue": dialogue,
                            "loc_id": location_id,
                            "witnesses": witnesses_json
                        }
                    )
                    sequence += 1

                # Record physical action
                if physical_action:
                    db.session.execute(
                        text("""
                            INSERT INTO memory.turn_history (
                                turn_id, game_state_id, turn_number,
                                character_id, sequence_number, action_type,
                                action_description, location_id, is_private, witnesses
                            ) VALUES (
                                :turn_id, :game_id, :turn_num,
                                :char_id, :seq, 'action',
                                :action, :loc_id, FALSE, CAST(:witnesses AS jsonb)
                            )
                        """),
                        {
                            "turn_id": str(uuid4()),
                            "game_id": str(game_id),
                            "turn_num": current_turn + 1,
                            "char_id": str(char_id),
                            "seq": sequence,
                            "action": physical_action,
                            "loc_id": location_id,
                            "witnesses": witnesses_json
                        }
                    )
                    sequence += 1

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
                    if dialogue:
                        combined_action_ai = f'says "{dialogue}"'
                    if physical_action:
                        if combined_action_ai:
                            combined_action_ai += f' and {physical_action}'
                        else:
                            combined_action_ai = physical_action

                    # Generate atmospheric description
                    atmos_desc_ai = generate_atmospheric_description(
                        character_name=char[1],
                        action_description=combined_action_ai if combined_action_ai else "acts",
                        location_name=location[0] if location else "Unknown",
                        location_description=location[1] if location else "",
                        other_characters=other_names_ai,
                        recent_history=recent_history_ai,
                        current_stance=char[6] if len(char) > 6 else None,
                        current_clothing=char[7] if len(char) > 7 else None
                    )

                    # Insert atmospheric description if generated
                    if atmos_desc_ai:
                        db.session.execute(
                            text("""
                                INSERT INTO memory.turn_history (
                                    turn_id, game_state_id, turn_number,
                                    character_id, sequence_number, action_type,
                                    action_description, location_id, is_private, witnesses
                                ) VALUES (
                                    :turn_id, :game_id, :turn_num,
                                    :char_id, :seq, 'atmospheric',
                                    :desc, :loc_id, FALSE, CAST(:witnesses AS jsonb)
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
                                "witnesses": witnesses_json
                            }
                        )
                except Exception as e:
                    logger.error(f"Error generating AI atmospheric description: {e}")
                    # Continue even if atmospheric description fails

                # Store emotional tone for this character to update after commit
                if emotional_tone:
                    char_emotional_tones[char_id] = (emotional_tone, char[1])  # Store tone and name

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

        db.session.commit()

        # Update AI character emotional states based on action emotional tones
        # (Do this after commit to avoid transaction issues)
        if char_emotional_tones:
            for char_id, (emotional_tone, char_name) in char_emotional_tones.items():
                if emotional_tone and emotional_tone.strip():
                    try:
                        # Use the emotional_tone directly as the emotional state
                        db.session.execute(
                            text("""
                                UPDATE character.character
                                SET current_emotional_state = :state
                                WHERE character_id = :char_id
                            """),
                            {
                                "state": emotional_tone,
                                "char_id": str(char_id)
                            }
                        )
                        db.session.commit()

                        logger.info(f"Updated AI character {char_name} emotional state to: {emotional_tone}")
                    except Exception as e:
                        logger.error(f"Error updating AI character emotional state: {e}")
                        # Continue even if emotional state update fails

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
