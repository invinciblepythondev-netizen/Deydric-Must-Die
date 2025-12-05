"""
Test script for in-game time tracking system

Demonstrates:
- Creating game state with time tracking
- Advancing time through multiple turns
- Day/night transitions
- Time formatting and categorization
- Integration with context assembly

Run with: python scripts/test_time_tracking.py
"""

import os
import sys
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.game_time import GameTime, GameState
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv('NEON_DATABASE_URL')
if not DATABASE_URL:
    logger.error("NEON_DATABASE_URL not set in environment")
    sys.exit(1)

# Create database connection
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def test_time_formatting():
    """Test time formatting functions."""
    logger.info("\n=== Testing Time Formatting ===")

    db = Session()

    test_times = [
        (0, "12:00 AM", "midnight"),
        (60, "1:00 AM", "early night"),
        (300, "5:00 AM", "dawn"),
        (420, "7:00 AM", "sunrise"),
        (720, "12:00 PM", "noon"),
        (1020, "5:00 PM", "late afternoon"),
        (1140, "7:00 PM", "sunset"),
        (1320, "10:00 PM", "late evening"),
    ]

    for minutes, expected_time, description in test_times:
        formatted = GameTime.format_time(db, minutes)
        category = GameTime.get_time_of_day_category(db, minutes)
        is_day = GameTime.is_daytime(db, minutes)

        logger.info(
            f"{expected_time:>10} ({minutes:>4} min) -> {formatted:>10} | "
            f"{category:>10} | {'☀️ DAY' if is_day else '🌙 NIGHT'} | {description}"
        )

        assert formatted == expected_time, f"Expected {expected_time}, got {formatted}"

    db.close()
    logger.info("✓ Time formatting tests passed")


def test_game_state_creation():
    """Test creating game state with time tracking."""
    logger.info("\n=== Testing Game State Creation ===")

    db = Session()

    # Create a new game starting at 7:00 AM on Day 1
    game_state_id = GameState.create(
        db,
        current_turn=1,
        game_day=1,
        minutes_since_midnight=420,  # 7:00 AM
        minutes_per_turn=6  # 10 turns = 1 hour
    )

    logger.info(f"Created game state: {game_state_id}")

    # Retrieve the game state
    game_state = GameState.get(db, game_state_id)

    assert game_state is not None, "Game state not found"
    assert game_state['game_day'] == 1, "Wrong day"
    assert game_state['minutes_since_midnight'] == 420, "Wrong time"
    assert game_state['minutes_per_turn'] == 6, "Wrong time rate"

    # Get time context
    time_context = GameTime.get_time_context(db, game_state_id)

    logger.info(f"  Day: {time_context['game_day']}")
    logger.info(f"  Time: {time_context['formatted_time']}")
    logger.info(f"  Time of Day: {time_context['time_of_day']}")
    logger.info(f"  Daytime: {time_context['is_daytime']}")

    assert time_context['formatted_time'] == "7:00 AM", "Wrong formatted time"
    assert time_context['time_of_day'] == "morning", "Wrong time category"
    assert time_context['is_daytime'] is True, "Should be daytime"

    db.close()
    logger.info("✓ Game state creation tests passed")

    return game_state_id


def test_time_advancement(game_state_id):
    """Test advancing time through turns."""
    logger.info("\n=== Testing Time Advancement ===")

    db = Session()

    # Advance through 10 turns (should be 1 hour)
    logger.info("Advancing 10 turns (1 hour)...")

    for i in range(10):
        result = GameTime.advance_turn(db, game_state_id)

        if i == 0 or i == 9:  # Log first and last
            logger.info(
                f"  Turn {result['current_turn']}: "
                f"Day {result['game_day']}, {result['formatted_time']} ({result['time_of_day']})"
            )

    # Should now be 8:00 AM
    time_context = GameTime.get_time_context(db, game_state_id)
    assert time_context['formatted_time'] == "8:00 AM", f"Expected 8:00 AM, got {time_context['formatted_time']}"

    logger.info(f"After 1 hour: {time_context['formatted_time']}")

    db.close()
    logger.info("✓ Time advancement tests passed")


def test_day_transition(game_state_id):
    """Test day rollover at midnight."""
    logger.info("\n=== Testing Day Transition ===")

    db = Session()

    # Get current state
    game_state = GameState.get(db, game_state_id)
    current_minutes = game_state['minutes_since_midnight']

    # Calculate turns needed to reach midnight
    # We're at 8:00 AM (480 minutes)
    # Need to reach 1440 (next day at 0:00)
    minutes_to_midnight = 1440 - current_minutes
    turns_to_midnight = minutes_to_midnight // 6

    logger.info(f"Current time: {current_minutes} minutes (8:00 AM)")
    logger.info(f"Need {turns_to_midnight} turns to reach midnight")

    # Advance to just before midnight
    for _ in range(turns_to_midnight - 1):
        GameTime.advance_turn(db, game_state_id)

    # Check we're late at night
    time_context = GameTime.get_time_context(db, game_state_id)
    logger.info(f"Before midnight: Day {time_context['game_day']}, {time_context['formatted_time']}")

    # Advance one more turn - should roll to Day 2
    result = GameTime.advance_turn(db, game_state_id)

    logger.info(f"After midnight: Day {result['game_day']}, {result['formatted_time']}")

    # Verify day rolled over
    time_context = GameTime.get_time_context(db, game_state_id)
    assert time_context['game_day'] == 2, f"Expected Day 2, got Day {time_context['game_day']}"
    assert time_context['minutes_since_midnight'] < 60, "Should be early morning"

    db.close()
    logger.info("✓ Day transition tests passed")


def test_context_integration(game_state_id):
    """Test integration with context assembly."""
    logger.info("\n=== Testing Context Integration ===")

    db = Session()

    # Reset to a known time (noon)
    db.execute(text("""
        UPDATE game.game_state
        SET minutes_since_midnight = 720
        WHERE game_state_id = :game_state_id
    """), {"game_state_id": str(game_state_id)})
    db.commit()

    time_context = GameTime.get_time_context(db, game_state_id)

    # Format for prompt
    time_string = GameTime.format_time_for_prompt(time_context)
    lighting = GameTime.get_lighting_description(time_context)

    logger.info(f"Time string: {time_string}")
    logger.info(f"Lighting: {lighting}")

    assert "12:00 PM" in time_string, "Time not in prompt string"
    assert "afternoon" in time_string, "Time category not in prompt string"

    # Test different times of day
    test_times = [
        (300, "dawn"),    # 5:00 AM
        (1140, "dusk"),   # 7:00 PM
        (1380, "night"),  # 11:00 PM
    ]

    for minutes, expected_category in test_times:
        db.execute(text("""
            UPDATE game.game_state
            SET minutes_since_midnight = :minutes
            WHERE game_state_id = :game_state_id
        """), {"game_state_id": str(game_state_id), "minutes": minutes})
        db.commit()

        time_context = GameTime.get_time_context(db, game_state_id)
        time_string = GameTime.format_time_for_prompt(time_context)

        logger.info(f"  {expected_category.upper()}: {time_string}")

        assert expected_category in time_string, f"Expected {expected_category} in prompt"

    db.close()
    logger.info("✓ Context integration tests passed")


def test_time_dependent_logic(game_state_id):
    """Test using time for game logic decisions."""
    logger.info("\n=== Testing Time-Dependent Logic ===")

    db = Session()

    # Test different times and their implications
    scenarios = [
        (420, "morning", True, "Good time for breakfast"),
        (780, "afternoon", True, "Market is busy"),
        (1140, "dusk", False, "Tavern filling up for evening"),
        (1380, "night", False, "Most shops closed, guards patrol"),
    ]

    for minutes, expected_tod, should_be_day, description in scenarios:
        # Set time
        db.execute(text("""
            UPDATE game.game_state
            SET minutes_since_midnight = :minutes
            WHERE game_state_id = :game_state_id
        """), {"game_state_id": str(game_state_id), "minutes": minutes})
        db.commit()

        time_context = GameTime.get_time_context(db, game_state_id)

        # Check categorization
        assert time_context['time_of_day'] == expected_tod, \
            f"Expected {expected_tod}, got {time_context['time_of_day']}"

        assert time_context['is_daytime'] == should_be_day, \
            f"Expected daytime={should_be_day}"

        logger.info(
            f"  {time_context['formatted_time']:>10} | "
            f"{time_context['time_of_day']:>10} | "
            f"{'☀️ DAY' if time_context['is_daytime'] else '🌙 NIGHT'} | "
            f"{description}"
        )

    db.close()
    logger.info("✓ Time-dependent logic tests passed")


def demonstrate_full_day():
    """Demonstrate a full 24-hour day cycle."""
    logger.info("\n=== Demonstrating Full Day Cycle ===")

    db = Session()

    # Create new game state starting at midnight
    game_state_id = GameState.create(
        db,
        current_turn=1,
        game_day=1,
        minutes_since_midnight=0,  # Midnight
        minutes_per_turn=60  # 1 turn = 1 hour for demo
    )

    logger.info("Starting at midnight, advancing 1 hour per turn:")
    logger.info("")

    previous_tod = None

    for turn in range(25):  # 24 hours + 1 to show rollover
        time_context = GameTime.get_time_context(db, game_state_id)

        # Log when time of day changes
        if time_context['time_of_day'] != previous_tod:
            icon = "☀️" if time_context['is_daytime'] else "🌙"
            logger.info(
                f"  Turn {turn:2d} | Day {time_context['game_day']} | "
                f"{time_context['formatted_time']:>10} | "
                f"{icon} {time_context['time_of_day']:>10} | "
                f"{GameTime.get_lighting_description(time_context)}"
            )
            previous_tod = time_context['time_of_day']

        # Advance
        if turn < 24:
            GameTime.advance_turn(db, game_state_id)

    db.close()
    logger.info("\n✓ Full day cycle demonstration complete")


def main():
    """Run all tests."""
    logger.info("=" * 70)
    logger.info("TIME TRACKING SYSTEM TEST SUITE")
    logger.info("=" * 70)

    try:
        # Basic tests
        test_time_formatting()
        game_state_id = test_game_state_creation()
        test_time_advancement(game_state_id)
        test_day_transition(game_state_id)
        test_context_integration(game_state_id)
        test_time_dependent_logic(game_state_id)

        # Full demonstration
        demonstrate_full_day()

        logger.info("\n" + "=" * 70)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 70)

    except AssertionError as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
