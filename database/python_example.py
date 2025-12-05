"""
Example: Using the Turn Sequence System in Python

This shows how to record a complex multi-action turn and query what different
characters witnessed.
"""

from sqlalchemy import text
from uuid import UUID

# Example game state
GAME_STATE_ID = "550e8400-e29b-41d4-a716-446655440000"
CHARACTER_A_ID = "a1111111-1111-1111-1111-111111111111"
CHARACTER_B_ID = "b2222222-2222-2222-2222-222222222222"
CHARACTER_C_ID = "c3333333-3333-3333-3333-333333333333"
TAVERN_LOCATION_ID = 1


def execute_complex_turn(db_session, turn_number):
    """
    Execute Character A's turn with multiple sequenced actions:
    1. Private thought (deceive B)
    2. Public speech (friendly greeting)
    3. Public physical action (reassuring touch)
    """

    # Sequence 0: Private Thought
    result = db_session.execute(text("""
        SELECT turn_history_create(
            p_game_state_id := :game_id,
            p_turn_number := :turn_num,
            p_character_id := :char_id,
            p_sequence_number := 0,
            p_action_type := 'think',
            p_action_description := :description,
            p_location_id := :location,
            p_is_private := true,
            p_significance_score := 0.8
        )
    """), {
        "game_id": GAME_STATE_ID,
        "turn_num": turn_number,
        "char_id": CHARACTER_A_ID,
        "description": "I can deceive Character B. They trust me, and I can use that to my advantage.",
        "location": TAVERN_LOCATION_ID
    })
    thought_id = result.scalar()
    print(f"✓ Recorded private thought: {thought_id}")

    # Sequence 1: Public Speech
    result = db_session.execute(text("""
        SELECT turn_history_create(
            p_game_state_id := :game_id,
            p_turn_number := :turn_num,
            p_character_id := :char_id,
            p_sequence_number := 1,
            p_action_type := 'speak',
            p_action_description := :description,
            p_location_id := :location,
            p_is_private := false,
            p_action_target_character_id := :target,
            p_witnesses := :witnesses,
            p_significance_score := 0.6
        )
    """), {
        "game_id": GAME_STATE_ID,
        "turn_num": turn_number,
        "char_id": CHARACTER_A_ID,
        "description": 'Character A smiles warmly and says, "I\'m glad you are here. I\'d like to help you."',
        "location": TAVERN_LOCATION_ID,
        "target": CHARACTER_B_ID,
        "witnesses": f'["{CHARACTER_B_ID}", "{CHARACTER_C_ID}"]'  # JSONB array
    })
    speech_id = result.scalar()
    print(f"✓ Recorded speech: {speech_id}")

    # Sequence 2: Physical Action
    result = db_session.execute(text("""
        SELECT turn_history_create(
            p_game_state_id := :game_id,
            p_turn_number := :turn_num,
            p_character_id := :char_id,
            p_sequence_number := 2,
            p_action_type := 'interact',
            p_action_description := :description,
            p_location_id := :location,
            p_is_private := false,
            p_action_target_character_id := :target,
            p_witnesses := :witnesses,
            p_significance_score := 0.5
        )
    """), {
        "game_id": GAME_STATE_ID,
        "turn_num": turn_number,
        "char_id": CHARACTER_A_ID,
        "description": "Character A reaches out and gently touches Character B's arm, a gesture of reassurance.",
        "location": TAVERN_LOCATION_ID,
        "target": CHARACTER_B_ID,
        "witnesses": f'["{CHARACTER_B_ID}", "{CHARACTER_C_ID}"]'
    })
    action_id = result.scalar()
    print(f"✓ Recorded physical action: {action_id}")

    db_session.commit()
    print(f"\n✓ Turn {turn_number} complete for Character A (3 sequenced actions)\n")


def get_character_perspective(db_session, character_id, character_name):
    """
    Get what a specific character witnessed (their own actions + public actions they saw)
    """
    print(f"--- {character_name}'s Perspective ---")

    result = db_session.execute(text("""
        SELECT * FROM turn_history_get_witnessed(:game_id, :char_id, 10)
    """), {
        "game_id": GAME_STATE_ID,
        "char_id": character_id
    })

    actions = result.fetchall()

    for action in actions:
        privacy_marker = "[PRIVATE] " if action.is_private else ""
        print(f"Turn {action.turn_number}.{action.sequence_number}: "
              f"{privacy_marker}{action.character_name} - {action.action_type}")
        print(f"  {action.action_description}")
        print()

    return actions


def get_full_turn_sequence(db_session, turn_number, character_id):
    """
    Get the complete sequence of actions for a character's turn (for display/debugging)
    """
    print(f"--- Full Turn {turn_number} Sequence ---")

    result = db_session.execute(text("""
        SELECT
            sequence_number, action_type, action_description,
            is_private, witnesses
        FROM memory.turn_history
        WHERE game_state_id = :game_id
          AND turn_number = :turn_num
          AND character_id = :char_id
        ORDER BY sequence_number ASC
    """), {
        "game_id": GAME_STATE_ID,
        "turn_num": turn_number,
        "char_id": character_id
    })

    actions = result.fetchall()

    for action in actions:
        privacy = "PRIVATE" if action.is_private else "PUBLIC"
        witness_count = len(action.witnesses) if action.witnesses else 0

        print(f"Seq {action.sequence_number}: [{privacy}] {action.action_type.upper()}")
        print(f"  {action.action_description}")
        print(f"  Witnesses: {witness_count}")
        print()

    return actions


def assemble_llm_context_for_character(db_session, character_id):
    """
    Assemble context for LLM when generating actions for a character.
    Only includes what the character actually knows.
    """
    result = db_session.execute(text("""
        SELECT * FROM turn_history_get_witnessed(:game_id, :char_id, 10)
    """), {
        "game_id": GAME_STATE_ID,
        "char_id": character_id
    })

    actions = result.fetchall()

    # Build context string for LLM prompt
    context_lines = []

    for action in actions:
        # Format differently for character's own private thoughts vs observed actions
        if action.is_private and action.character_id == character_id:
            # This is the character's own private thought
            context_lines.append(f"[YOUR PRIVATE THOUGHT] {action.action_description}")
        else:
            # This is something they witnessed (public action)
            context_lines.append(f"{action.character_name}: {action.action_description}")

    context_string = "\n".join(context_lines)

    return context_string


# Example usage:
def main():
    """
    Example workflow
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    # Connect to database
    DATABASE_URL = os.getenv('NEON_DATABASE_URL')
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Execute a complex turn
    print("="*60)
    print("EXECUTING CHARACTER A'S TURN 15")
    print("="*60 + "\n")
    execute_complex_turn(session, turn_number=15)

    # Show full sequence (debugging view)
    get_full_turn_sequence(session, turn_number=15, character_id=CHARACTER_A_ID)

    # Show what each character witnessed
    print("\n" + "="*60)
    print("WHAT EACH CHARACTER KNOWS")
    print("="*60 + "\n")

    # Character A (the actor) sees EVERYTHING including their private thought
    get_character_perspective(session, CHARACTER_A_ID, "Character A")

    # Character B (witness) sees only public actions
    get_character_perspective(session, CHARACTER_B_ID, "Character B")

    # Character C (also witness) sees only public actions
    get_character_perspective(session, CHARACTER_C_ID, "Character C")

    # Assemble context for LLM (Character B's next turn)
    print("\n" + "="*60)
    print("LLM CONTEXT FOR CHARACTER B")
    print("="*60 + "\n")

    context = assemble_llm_context_for_character(session, CHARACTER_B_ID)
    print(context)

    session.close()


if __name__ == "__main__":
    main()
