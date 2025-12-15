"""
Backfill Memory Summary Embeddings to Qdrant

This script embeds existing memory summaries into Qdrant vector database
for semantic search. It processes summaries that haven't been embedded yet.

Usage:
    python scripts/backfill_summary_embeddings.py [--batch-size N] [--game-id UUID] [--character-id UUID]

Options:
    --batch-size N: Process N summaries at a time (default: 10)
    --game-id UUID: Only process summaries for specific game (optional)
    --character-id UUID: Only process summaries for specific character (optional)
    --use-condensed: Embed condensed version instead of descriptive (default: descriptive)
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from uuid import UUID

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment
load_dotenv()

# Import services
from services.vector_store import VectorStoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_summaries(
    batch_size: int = 10,
    game_state_id: str = None,
    character_id: str = None,
    use_descriptive: bool = True
):
    """
    Backfill memory summaries into Qdrant.

    Args:
        batch_size: Number of summaries to process at a time
        game_state_id: Optional game state UUID filter
        character_id: Optional character UUID filter
        use_descriptive: Whether to embed descriptive (True) or condensed (False) version
    """
    # Get database URL
    database_url = os.getenv("NEON_DATABASE_URL")
    if not database_url:
        logger.error("NEON_DATABASE_URL not set in .env")
        return False

    # Create database connection
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db_session = SessionLocal()

    # Initialize vector store
    try:
        vector_store = VectorStoreService(collection_name="game_memories")
        logger.info(f"Connected to Qdrant. Current summary count: {vector_store.count_summaries()}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return False

    try:
        # Get summaries that need embedding
        logger.info("Fetching summaries that need embedding...")

        summaries = db_session.execute(
            text("""
                SELECT * FROM memory_summary_get_not_embedded(
                    :game_id, :char_id, :limit
                )
            """),
            {
                "game_id": game_state_id,
                "char_id": character_id,
                "limit": 1000  # Get all pending
            }
        ).fetchall()

        if not summaries:
            logger.info("No summaries need embedding. All up to date!")
            return True

        logger.info(f"Found {len(summaries)} summaries to embed")

        # Process in batches
        total_embedded = 0
        total_failed = 0

        for i in range(0, len(summaries), batch_size):
            batch = summaries[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} summaries)...")

            for summary in batch:
                (
                    summary_id,
                    game_id,
                    char_id,
                    window_type,
                    start_turn,
                    end_turn,
                    descriptive_summary,
                    condensed_summary
                ) = summary

                try:
                    # Get character name for metadata
                    character_result = db_session.execute(
                        text("SELECT name FROM character.character WHERE character_id = :id"),
                        {"id": str(char_id)}
                    ).fetchone()
                    character_name = character_result[0] if character_result else "Unknown"

                    # Prepare metadata
                    metadata = {
                        'game_state_id': str(game_id),
                        'character_id': str(char_id),
                        'character_name': character_name,
                        'window_type': window_type,
                        'start_turn': start_turn,
                        'end_turn': end_turn,
                        'turn_span': end_turn - start_turn + 1
                    }

                    # Choose which version to embed
                    text_to_embed = descriptive_summary if use_descriptive else condensed_summary
                    version = 'descriptive' if use_descriptive else 'condensed'

                    # Embed in Qdrant
                    success = vector_store.add_summary(
                        summary_id=str(summary_id),
                        text=text_to_embed,
                        metadata=metadata,
                        use_descriptive=use_descriptive
                    )

                    if success:
                        # Mark as embedded in database
                        db_session.execute(
                            text("""
                                SELECT memory_summary_mark_embedded(
                                    :summary_id, :embedding_id, :version
                                )
                            """),
                            {
                                "summary_id": str(summary_id),
                                "embedding_id": str(summary_id),
                                "version": version
                            }
                        )
                        db_session.commit()
                        total_embedded += 1
                        logger.info(f"  ✓ Embedded summary {summary_id} ({window_type}, turns {start_turn}-{end_turn})")
                    else:
                        total_failed += 1
                        logger.warning(f"  ✗ Failed to embed summary {summary_id}")

                except Exception as e:
                    total_failed += 1
                    logger.error(f"  ✗ Error processing summary {summary_id}: {e}")
                    db_session.rollback()

            logger.info(f"Batch complete. Embedded: {total_embedded}, Failed: {total_failed}")

        logger.info("=" * 60)
        logger.info(f"Backfill complete!")
        logger.info(f"  Total embedded: {total_embedded}")
        logger.info(f"  Total failed: {total_failed}")
        logger.info(f"  Current Qdrant summary count: {vector_store.count_summaries()}")
        logger.info("=" * 60)

        return total_failed == 0

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return False

    finally:
        db_session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill memory summaries into Qdrant vector database"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of summaries to process at a time (default: 10)"
    )
    parser.add_argument(
        "--game-id",
        type=str,
        default=None,
        help="Only process summaries for this game state UUID"
    )
    parser.add_argument(
        "--character-id",
        type=str,
        default=None,
        help="Only process summaries for this character UUID"
    )
    parser.add_argument(
        "--use-condensed",
        action="store_true",
        help="Embed condensed version instead of descriptive"
    )

    args = parser.parse_args()

    # Validate UUIDs if provided
    if args.game_id:
        try:
            UUID(args.game_id)
        except ValueError:
            logger.error(f"Invalid game-id UUID: {args.game_id}")
            sys.exit(1)

    if args.character_id:
        try:
            UUID(args.character_id)
        except ValueError:
            logger.error(f"Invalid character-id UUID: {args.character_id}")
            sys.exit(1)

    logger.info("Starting memory summary backfill...")
    logger.info(f"  Batch size: {args.batch_size}")
    logger.info(f"  Game filter: {args.game_id or 'All games'}")
    logger.info(f"  Character filter: {args.character_id or 'All characters'}")
    logger.info(f"  Version: {'Condensed' if args.use_condensed else 'Descriptive'}")
    logger.info("=" * 60)

    success = backfill_summaries(
        batch_size=args.batch_size,
        game_state_id=args.game_id,
        character_id=args.character_id,
        use_descriptive=not args.use_condensed
    )

    if success:
        logger.info("Backfill completed successfully!")
        sys.exit(0)
    else:
        logger.error("Backfill completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
