"""
Memory Summarization Service

Generates tiered memory summaries for characters using LLMs.
Creates both descriptive (for large context models) and condensed versions.

SUMMARY TIERS:
- recent_10: Last 10 turns
- rolling_50: Last 50 turns (rolling window)
- rolling_100: Last 100 turns (rolling window)
- deep_720: Last 720 turns (~6 hours in-game at 30s/turn)
- deep_1440: Last 1440 turns (~12 hours)
- deep_2880: Last 2880 turns (~24 hours)
- deep_5760: Last 5760 turns (~48 hours)
"""

import logging
from typing import Dict, List, Any, Tuple
from uuid import UUID
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MemorySummarizer:
    """
    Generates memory summaries at different time tiers for characters.

    Each summary has two versions:
    - Descriptive: Rich narrative prose (200-400 words) for large context models (128K+ tokens)
    - Condensed: Concise bullet-point style (50-100 words) for small context models (8-32K tokens)
    """

    def __init__(self, llm_provider, vector_store=None):
        """
        Initialize summarizer with LLM provider.

        Args:
            llm_provider: LLM provider instance (for generating summaries)
            vector_store: Optional VectorStoreService instance (for embedding summaries)
        """
        self.llm_provider = llm_provider
        self.vector_store = vector_store

    def generate_summary_for_window(
        self,
        db_session,
        game_state_id: UUID,
        character_id: UUID,
        window_type: str,
        start_turn: int,
        end_turn: int
    ) -> Tuple[str, str]:
        """
        Generate both descriptive and condensed summaries for a turn window.

        Args:
            db_session: Database session
            game_state_id: Game state UUID
            character_id: Character UUID
            window_type: Type of window (recent_10, rolling_50, etc.)
            start_turn: Starting turn number
            end_turn: Ending turn number (inclusive)

        Returns:
            Tuple of (descriptive_summary, condensed_summary)
        """
        # Get character name using stored procedure
        character_result = db_session.execute(
            text("SELECT * FROM character_get(:id)"),
            {"id": str(character_id)}
        ).fetchone()

        if not character_result:
            raise ValueError(f"Character {character_id} not found")

        character_name = character_result.name

        # Get turn history for this character in this window
        turn_history = db_session.execute(
            text("""
                SELECT
                    turn_number,
                    sequence_number,
                    action_type,
                    action_description,
                    is_private
                FROM memory.turn_history
                WHERE game_state_id = :game_id
                  AND turn_number BETWEEN :start_turn AND :end_turn
                  AND (
                    character_id = :character_id
                    OR :character_id = ANY(
                        SELECT jsonb_array_elements_text(witnesses)::uuid
                    )
                  )
                  AND action_type != 'atmospheric'
                ORDER BY turn_number ASC, sequence_number ASC
            """),
            {
                "game_id": str(game_state_id),
                "character_id": str(character_id),
                "start_turn": start_turn,
                "end_turn": end_turn
            }
        ).fetchall()

        if not turn_history:
            logger.warning(f"No turn history found for {character_name} in turns {start_turn}-{end_turn}")
            return (
                f"No significant events occurred for {character_name} during turns {start_turn}-{end_turn}.",
                f"No events (turns {start_turn}-{end_turn})."
            )

        # Format turn history for LLM
        history_lines = []
        for row in turn_history:
            turn_num, seq_num, action_type, description, is_private = row
            privacy_tag = " [private]" if is_private else ""
            history_lines.append(f"Turn {turn_num}.{seq_num} ({action_type}): {description}{privacy_tag}")

        history_text = "\n".join(history_lines)
        turn_count = end_turn - start_turn + 1

        # Build prompt for summary generation
        system_prompt = """You are a narrative summarizer for a dark fantasy text adventure game.

Your task is to create TWO versions of a summary for a character's experiences:

1. DESCRIPTIVE VERSION (200-400 words):
   - Rich narrative prose suitable for large context models
   - Include emotional nuances, motivations, and character development
   - Capture the narrative arc and key moments
   - Write in third-person past tense from an omniscient narrator perspective

2. CONDENSED VERSION (50-100 words):
   - Concise bullet-point style suitable for small context models
   - Focus only on most significant events and outcomes
   - Omit minor details and atmospheric descriptions
   - Still maintain narrative coherence

Return the summaries as JSON:
{
  "descriptive_summary": "...",
  "condensed_summary": "..."
}

IMPORTANT: Return ONLY valid JSON. No markdown code blocks, no extra text."""

        user_prompt = f"""Character: {character_name}
Time Period: Turns {start_turn}-{end_turn} ({turn_count} turns, ~{turn_count * 0.5:.0f} minutes in-game)
Window Type: {window_type}

Events that {character_name} experienced or witnessed:
{history_text}

Generate both descriptive and condensed summaries of this period from {character_name}'s perspective."""

        # Retry logic: Try up to 3 times (initial + 2 retries) if JSON parsing fails
        max_attempts = 3
        last_error = None

        try:
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        print(f"\n[MemorySummarizer] Retry attempt {attempt}/{max_attempts-1}")
                        logger.info(f"Retrying summary generation (attempt {attempt + 1}/{max_attempts})")

                    # Generate summary using LLM
                    logger.info(f"Generating summary for {character_name}, turns {start_turn}-{end_turn} ({window_type})")

                    # ResilientActionGenerator's generate() method already handles fallback automatically
                    # It will try providers in order if one refuses due to mature content
                    print(f"\n[MemorySummarizer] Calling LLM to generate summary for {character_name}, turns {start_turn}-{end_turn}")
                    print(f"[MemorySummarizer] System prompt length: {len(system_prompt)} chars")
                    print(f"[MemorySummarizer] User prompt length: {len(user_prompt)} chars")

                    response = self.llm_provider.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,  # Lower temperature for consistent summaries
                        max_tokens=1024
                    )

                    logger.info(f"Received response from LLM: {len(response)} chars")
                    print(f"\n[MemorySummarizer] Received response from LLM: {len(response)} chars")
                    print(f"[MemorySummarizer] Response preview:\n{response[:300]}\n")
                    logger.debug(f"Response preview: {response[:200]}...")

                    # Parse JSON response
                    import json
                    import re

                    json_str = response.strip()

                    # Extract JSON from markdown if needed
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()

                    # Clean trailing commas
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                    # Try to parse JSON, handling control character errors from some providers
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError as json_error:
                        # If it's a control character error, try to fix it
                        if "Invalid control character" in str(json_error):
                            logger.warning(f"JSON contains control characters, attempting to clean: {json_error}")
                            # Replace common unescaped control characters
                            # This handles cases where LLMs put literal newlines/tabs in JSON strings
                            cleaned_json = json_str
                            # Replace unescaped control characters within string values
                            # We need to be careful to only replace inside quoted strings
                            # Simple approach: escape common control chars
                            cleaned_json = cleaned_json.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                            # Try parsing the cleaned version
                            try:
                                result = json.loads(cleaned_json)
                                logger.info("Successfully parsed JSON after cleaning control characters")
                            except json.JSONDecodeError as cleaned_error:
                                logger.error(f"Still failed after cleaning: {cleaned_error}")
                                logger.error(f"Attempted to parse: {cleaned_json[:500]}...")
                                raise
                        else:
                            # Different JSON error, try regex extraction as fallback
                            logger.warning(f"JSON parse error: {json_error}")
                            logger.warning(f"Attempting regex extraction from: {json_str[:200]}...")

                            # Try to extract fields using regex
                            descriptive_match = re.search(r'"descriptive_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str, re.DOTALL)
                            condensed_match = re.search(r'"condensed_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str, re.DOTALL)

                            if descriptive_match and condensed_match:
                                descriptive = descriptive_match.group(1).replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"')
                                condensed = condensed_match.group(1).replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"')
                                logger.info("Successfully extracted summaries using regex")
                                return (descriptive, condensed)
                            else:
                                logger.error("Could not extract summaries using regex")
                                raise

                    descriptive = result.get('descriptive_summary', '').strip()
                    condensed = result.get('condensed_summary', '').strip()

                    if not descriptive or not condensed:
                        logger.error(f"Missing summaries in response. Keys found: {list(result.keys())}")
                        logger.error(f"Response content: {json_str[:500]}...")
                        print(f"\n[MemorySummarizer ERROR] Missing summaries in JSON!")
                        print(f"Keys found: {list(result.keys())}")
                        print(f"Full result: {result}")
                        raise ValueError("Missing descriptive or condensed summary in LLM response")

                    logger.info(f"Successfully generated summaries: {len(descriptive)} / {len(condensed)} chars")
                    print(f"[MemorySummarizer SUCCESS] Generated summaries: descriptive={len(descriptive)} chars, condensed={len(condensed)} chars")
                    print(f"Descriptive summary preview: {descriptive[:150]}...")

                    # Success! Return the summaries
                    return (descriptive, condensed)

                except Exception as attempt_error:
                    # Store the error for potential retry
                    last_error = attempt_error
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {attempt_error}")
                    print(f"[MemorySummarizer] Attempt {attempt + 1}/{max_attempts} failed: {str(attempt_error)[:100]}")

                    # If this was the last attempt, we'll fall through to the outer exception handler
                    if attempt < max_attempts - 1:
                        # Not the last attempt, continue to retry
                        continue
                    else:
                        # Last attempt failed, re-raise to outer handler
                        raise

        except Exception as e:
            logger.error(f"Error generating summary after {max_attempts} attempts: {e}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Character: {character_name}, Window: {window_type}, Turns: {start_turn}-{end_turn}")

            print(f"\n[MemorySummarizer ERROR] All {max_attempts} attempts failed!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Character: {character_name}, Window: {window_type}, Turns: {start_turn}-{end_turn}")

            # Check if this is an AllProvidersFailedError from resilient generator
            if "AllProvidersFailedError" in str(type(e)):
                logger.error("All LLM providers failed for summary generation!")
                logger.error(f"Last error from providers: {getattr(e, 'last_error', 'Unknown')}")
                print(f"[MemorySummarizer ERROR] All LLM providers failed!")
                print(f"Last error from providers: {getattr(e, 'last_error', 'Unknown')}")
                if hasattr(e, 'attempted_providers'):
                    print(f"Attempted providers: {e.attempted_providers}")

            # Fallback to basic summary after all retries exhausted
            logger.warning(f"Using fallback generic summary after {max_attempts} failed attempts")
            print(f"[MemorySummarizer WARNING] Using fallback generic summary after all retries exhausted\n")
            descriptive = f"{character_name} experienced {len(turn_history)} events during turns {start_turn}-{end_turn}."
            condensed = f"Turns {start_turn}-{end_turn}: {len(turn_history)} events."
            return (descriptive, condensed)

    def generate_summaries_for_character(
        self,
        db_session,
        game_state_id: UUID,
        character_id: UUID,
        current_turn: int
    ) -> Dict[str, Any]:
        """
        Generate all needed summaries for a character at current turn.

        Checks which summaries need to be generated and creates them.

        Args:
            db_session: Database session
            game_state_id: Game state UUID
            character_id: Character UUID
            current_turn: Current turn number

        Returns:
            Dictionary with generation results
        """
        logger.info(f"Checking summaries needed for character {character_id} at turn {current_turn}")

        # Check which summaries are needed
        needed = db_session.execute(
            text("SELECT * FROM memory_summary_check_needed(:game_id, :char_id, :turn)"),
            {
                "game_id": str(game_state_id),
                "char_id": str(character_id),
                "turn": current_turn
            }
        ).fetchall()

        results = {
            'generated': [],
            'skipped': [],
            'errors': []
        }

        for row in needed:
            window_type, start_turn, end_turn, is_needed, reason = row

            if not is_needed:
                results['skipped'].append({
                    'window_type': window_type,
                    'reason': reason
                })
                continue

            try:
                logger.info(f"Generating {window_type} summary for turns {start_turn}-{end_turn}...")

                # Generate summaries
                descriptive, condensed = self.generate_summary_for_window(
                    db_session,
                    game_state_id,
                    character_id,
                    window_type,
                    start_turn,
                    end_turn
                )

                # Store in database
                summary_id = db_session.execute(
                    text("""
                        SELECT memory_summary_upsert(
                            :game_id, :char_id, :window_type,
                            :start_turn, :end_turn,
                            :descriptive, :condensed
                        )
                    """),
                    {
                        "game_id": str(game_state_id),
                        "char_id": str(character_id),
                        "window_type": window_type,
                        "start_turn": start_turn,
                        "end_turn": end_turn,
                        "descriptive": descriptive,
                        "condensed": condensed
                    }
                ).scalar()

                db_session.commit()

                # Embed in vector store if available
                embedding_success = False
                if self.vector_store:
                    try:
                        # Get character name for metadata using stored procedure
                        character_result = db_session.execute(
                            text("SELECT * FROM character_get(:id)"),
                            {"id": str(character_id)}
                        ).fetchone()
                        character_name = character_result.name if character_result else "Unknown"

                        # Prepare metadata
                        metadata = {
                            'game_state_id': str(game_state_id),
                            'character_id': str(character_id),
                            'character_name': character_name,
                            'window_type': window_type,
                            'start_turn': start_turn,
                            'end_turn': end_turn,
                            'turn_span': end_turn - start_turn + 1
                        }

                        # Embed descriptive version by default
                        embedding_success = self.vector_store.add_summary(
                            summary_id=str(summary_id),
                            text=descriptive,
                            metadata=metadata,
                            use_descriptive=True
                        )

                        if embedding_success:
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
                                    "version": "descriptive"
                                }
                            )
                            db_session.commit()
                            logger.info(f"Embedded summary {summary_id} in Qdrant")
                        else:
                            logger.warning(f"Failed to embed summary {summary_id} in Qdrant")

                    except Exception as embed_error:
                        logger.error(f"Error embedding summary: {embed_error}", exc_info=True)

                results['generated'].append({
                    'window_type': window_type,
                    'turn_range': f"{start_turn}-{end_turn}",
                    'summary_id': str(summary_id),
                    'descriptive_len': len(descriptive),
                    'condensed_len': len(condensed),
                    'embedded': embedding_success
                })

                logger.info(f"Stored {window_type} summary: {summary_id}")

            except Exception as e:
                logger.error(f"Error generating {window_type} summary: {e}", exc_info=True)
                # Rollback the failed transaction so subsequent iterations can proceed
                db_session.rollback()
                results['errors'].append({
                    'window_type': window_type,
                    'error': str(e)
                })

        return results

    def get_summaries_for_context(
        self,
        db_session,
        game_state_id: UUID,
        character_id: UUID,
        use_descriptive: bool = True,
        exclude_recent_n_turns: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all relevant summaries for a character to use in LLM context.

        Args:
            db_session: Database session
            game_state_id: Game state UUID
            character_id: Character UUID
            use_descriptive: If True, use descriptive summaries; if False, use condensed
            exclude_recent_n_turns: Exclude windows that overlap with recent N turns
                                   (those turns will be in working memory instead)

        Returns:
            List of summary dictionaries ordered by recency
        """
        summaries = db_session.execute(
            text("""
                SELECT * FROM memory_summary_get_latest_tiers(
                    :game_id, :char_id, :use_descriptive
                )
            """),
            {
                "game_id": str(game_state_id),
                "char_id": str(character_id),
                "use_descriptive": use_descriptive
            }
        ).fetchall()

        # Get current turn to filter out overlapping windows
        current_turn_result = db_session.execute(
            text("SELECT current_turn FROM game.game_state WHERE game_state_id = :id"),
            {"id": str(game_state_id)}
        ).fetchone()

        current_turn = current_turn_result[0] if current_turn_result else 0
        cutoff_turn = current_turn - exclude_recent_n_turns

        result = []
        for row in summaries:
            window_type, start_turn, end_turn, summary_text, turn_span = row

            # Skip if this window overlaps with recent working memory
            if end_turn > cutoff_turn:
                continue

            result.append({
                'window_type': window_type,
                'start_turn': start_turn,
                'end_turn': end_turn,
                'summary': summary_text,
                'turn_span': turn_span
            })

        return result

    def search_relevant_summaries(
        self,
        query: str,
        character_id: UUID = None,
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memory summaries using semantic similarity.

        Args:
            query: The search query text (e.g., "conflicts with guards")
            character_id: Optional character UUID to filter by
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of relevant summary dictionaries
        """
        if not self.vector_store:
            logger.warning("Vector store not available for summary search")
            return []

        try:
            if character_id:
                results = self.vector_store.search_summaries_by_character(
                    query=query,
                    character_id=str(character_id),
                    limit=limit,
                    score_threshold=score_threshold
                )
            else:
                results = self.vector_store.search_summaries(
                    query=query,
                    limit=limit,
                    score_threshold=score_threshold
                )

            logger.info(f"Found {len(results)} relevant summaries for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Error searching summaries: {e}", exc_info=True)
            return []
