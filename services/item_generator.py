"""
Item Generator Service - LLM-powered item creation

Generates detailed item descriptions for game locations using LLM with automatic fallback.
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class ItemGenerator:
    """Generates items for locations using LLM."""

    def __init__(self, llm_provider):
        """
        Initialize item generator.

        Args:
            llm_provider: Resilient LLM provider (ResilientActionGenerator)
        """
        self.llm_provider = llm_provider

    def generate_items_for_location(
        self,
        location_name: str,
        location_description: str,
        location_id: int,
        created_turn: int = 0,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate items that would be found in a location.

        Args:
            location_name: Name of the location
            location_description: Detailed description of the location
            location_id: Database location ID
            created_turn: Turn number when items were created (negative for pre-game)
            max_retries: Number of retries on invalid JSON

        Returns:
            List of item dictionaries
        """
        system_prompt = """You are generating a list of items found in a location for a dark fantasy text adventure game.

For each item, provide complete details following these scales:

SIZE SCALE (1-10000):
- 1-10: Tiny items (pin, needle, coin, button)
- 11-50: Small items (ring, key, scroll, letter, knife)
- 51-150: Medium items (book, dagger, shirt, bottle, candlestick)
- 151-500: Large items (sword, chair, cloak, bag, boots)
- 501-2000: Very large items (chest, table, wardrobe, door, rug)
- 2001-10000: Massive items (four-poster bed, carriage, large furniture, tapestry)

WEIGHT SCALE (1-10000):
- 1-10: Feather-light (paper, cloth, feather, cobweb)
- 11-50: Light (book, empty bottle, dagger, letter)
- 51-200: Medium (sword, full bottle, small bag of coins, shirt)
- 201-800: Heavy (chair, armor, full backpack, boots)
- 801-3000: Very heavy (chest of items, table, person, wardrobe)
- 3001-10000: Extremely heavy (wardrobe full of clothes, bed, stone statue)

CAPACITY SCALE (0 to 80% of size):
**CRITICAL**: Capacity must be LESS than size! Items have walls, structure, etc.
- 0: Cannot contain items (most items)
- For containers, capacity should be 50-80% of size:
  * Thin-walled containers (bag, satchel): ~70-80% of size
  * Thick-walled containers (chest, wardrobe): ~50-60% of size
- Examples:
  * Small chest (size=600) → capacity ~400 max (NOT 4000!)
  * Wardrobe (size=1500) → capacity ~1000 max
  * Backpack (size=300) → capacity ~220 max
  * Large bed (size=5000) → capacity 0 (cannot contain items)
- A container CANNOT hold items larger than its capacity
- Total size of contained items cannot exceed capacity

Return a JSON array with 5-15 notable items:
[
  {
    "item_type": "furniture|clothing|weapon|tool|decoration|container|consumable|other",
    "item_name": "Display name for the item",
    "item_description": "Detailed description (2-3 sentences) including material, condition, notable features",
    "item_description_short": "Brief one-sentence description",
    "size": <number 1-10000>,
    "weight": <number 1-10000>,
    "capacity": <number 0-100000>
  }
]

IMPORTANT:
- Include mix of furniture, decorations, containers, and smaller items
- Be realistic about scales (a pin weighs almost nothing, a bed is massive)
- Capacity should match item type (only containers have capacity > 0)
- Descriptions should match the dark fantasy gothic aesthetic
- Include items mentioned in the location description
- Return ONLY valid JSON, no markdown, no extra text"""

        user_prompt = f"""LOCATION: {location_name}

DESCRIPTION:
{location_description}

Generate a comprehensive list of items that would be found in this location. Include furniture, decorations, containers, and smaller notable items. Be specific and atmospheric."""

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying item generation (attempt {attempt + 1}/{max_retries + 1})")

                # Generate using resilient provider
                logger.info(f"Generating items for location: {location_name}")
                response = self.llm_provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7,  # Some creativity but stay realistic
                    max_tokens=2048
                )

                logger.debug(f"Received response ({len(response)} chars)")

                # Parse JSON
                json_str = response.strip()

                # Extract from markdown if needed
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                # Clean trailing commas
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                # Parse JSON
                items_data = json.loads(json_str)

                if not isinstance(items_data, list):
                    raise ValueError("Response is not a JSON array")

                # Validate and enrich each item
                items = []
                for idx, item_data in enumerate(items_data):
                    # Validate required fields
                    required = ['item_type', 'item_name', 'item_description', 'item_description_short', 'size', 'weight', 'capacity']
                    missing = [f for f in required if f not in item_data]
                    if missing:
                        logger.warning(f"Item {idx} missing fields: {missing}, skipping")
                        continue

                    # Validate ranges
                    if not (1 <= item_data['size'] <= 10000):
                        logger.warning(f"Item {idx} size out of range: {item_data['size']}, clamping")
                        item_data['size'] = max(1, min(10000, item_data['size']))

                    if not (1 <= item_data['weight'] <= 10000):
                        logger.warning(f"Item {idx} weight out of range: {item_data['weight']}, clamping")
                        item_data['weight'] = max(1, min(10000, item_data['weight']))

                    # Validate capacity (must be <= 80% of size)
                    max_capacity = int(item_data['size'] * 0.8)
                    if item_data['capacity'] > max_capacity:
                        logger.warning(
                            f"Item {idx} ({item_data['item_name']}) capacity ({item_data['capacity']}) "
                            f"exceeds 80% of size ({item_data['size']}). Clamping to {max_capacity}"
                        )
                        item_data['capacity'] = max_capacity

                    if item_data['capacity'] < 0:
                        logger.warning(f"Item {idx} has negative capacity, setting to 0")
                        item_data['capacity'] = 0

                    # Add metadata
                    item_data['item_id'] = uuid4()
                    item_data['location_id'] = location_id
                    item_data['created_turn'] = created_turn
                    item_data['contained_by_item_id'] = None
                    item_data['carried_by_character_id'] = None
                    item_data['current_state'] = None

                    # Add hybrid approach fields with defaults
                    item_data['importance_level'] = item_data.get('importance_level', 'mundane')
                    item_data['visibility_level'] = item_data.get('visibility_level', 'visible')
                    item_data['position_type'] = None
                    item_data['positioned_at_item_id'] = None
                    item_data['has_contents'] = item_data['capacity'] > 0  # Containers may have contents
                    item_data['contents_generated'] = False  # Not generated yet
                    item_data['worn_slot'] = None
                    item_data['carry_method'] = None

                    items.append(item_data)

                if not items:
                    raise ValueError("No valid items generated")

                logger.info(f"Successfully generated {len(items)} items for {location_name}")
                return items

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

            except Exception as e:
                logger.error(f"Error generating items (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

        return []

    def generate_obvious_items(
        self,
        location_name: str,
        location_description: str,
        location_id: int,
        max_items: int = 7,
        created_turn: int = 0,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate only obvious and crucial items for initial room population.

        This is more token-efficient than generating all items upfront.
        Hidden/searchable items can be generated later when discovered.

        Args:
            location_name: Name of the location
            location_description: Detailed description of the location
            location_id: Database location ID
            max_items: Maximum number of items to generate (default 7)
            created_turn: Turn number when items were created (negative for pre-game)
            max_retries: Number of retries on invalid JSON

        Returns:
            List of obvious/crucial item dictionaries
        """
        system_prompt = f"""You are generating OBVIOUS and CRUCIAL items for a dark fantasy text adventure game room.

IMPORTANT:
- Generate ONLY {max_items} items maximum
- Focus on:
  * Large furniture (beds, tables, wardrobes, chairs)
  * Obvious decorations (tapestries, paintings, chandeliers)
  * Crucial plot items (if any mentioned in description)
  * Obvious containers (chests, wardrobes, desks)
- DO NOT include hidden/searchable items (those come later)
- Mark importance level: "crucial" for plot items, "notable" for large furniture, "mundane" for decorations

SIZE, WEIGHT, CAPACITY scales same as before.

Return JSON array with importance_level and visibility_level fields:
[
  {{
    "item_type": "furniture|clothing|weapon|tool|decoration|container|consumable|other",
    "item_name": "Display name",
    "item_description": "Detailed description (2-3 sentences)",
    "item_description_short": "Brief one-sentence description",
    "size": <number 1-10000>,
    "weight": <number 1-10000>,
    "capacity": <number 0-capacity_limit>,
    "importance_level": "crucial|notable|mundane",
    "visibility_level": "obvious"
  }}
]

CRITICAL:
- Capacity MUST be ≤ 80% of size
- Return ONLY valid JSON, no markdown, no extra text
- Maximum {max_items} items"""

        user_prompt = f"""LOCATION: {location_name}

DESCRIPTION:
{location_description}

Generate {max_items} or fewer OBVIOUS items that would immediately catch attention upon entering this room. Focus on large furniture, obvious decorations, and any crucial plot items. Mark importance appropriately."""

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying obvious item generation (attempt {attempt + 1}/{max_retries + 1})")

                logger.info(f"Generating obvious items for location: {location_name}")
                response = self.llm_provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=2048
                )

                logger.debug(f"Received response ({len(response)} chars)")

                # Parse JSON
                json_str = response.strip()

                # Extract from markdown if needed
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                # Clean trailing commas
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                # Parse JSON
                items_data = json.loads(json_str)

                if not isinstance(items_data, list):
                    raise ValueError("Response is not a JSON array")

                # Validate and enrich each item
                items = []
                for idx, item_data in enumerate(items_data):
                    required = ['item_type', 'item_name', 'item_description', 'item_description_short', 'size', 'weight', 'capacity']
                    missing = [f for f in required if f not in item_data]
                    if missing:
                        logger.warning(f"Item {idx} missing fields: {missing}, skipping")
                        continue

                    # Validate ranges
                    if not (1 <= item_data['size'] <= 10000):
                        logger.warning(f"Item {idx} size out of range, clamping")
                        item_data['size'] = max(1, min(10000, item_data['size']))

                    if not (1 <= item_data['weight'] <= 10000):
                        logger.warning(f"Item {idx} weight out of range, clamping")
                        item_data['weight'] = max(1, min(10000, item_data['weight']))

                    # Validate capacity
                    max_capacity = int(item_data['size'] * 0.8)
                    if item_data['capacity'] > max_capacity:
                        logger.warning(f"Item {idx} capacity exceeds 80% of size, clamping to {max_capacity}")
                        item_data['capacity'] = max_capacity

                    if item_data['capacity'] < 0:
                        item_data['capacity'] = 0

                    # Add metadata
                    item_data['item_id'] = uuid4()
                    item_data['location_id'] = location_id
                    item_data['created_turn'] = created_turn
                    item_data['contained_by_item_id'] = None
                    item_data['carried_by_character_id'] = None
                    item_data['current_state'] = None

                    # Ensure importance/visibility are set
                    item_data['importance_level'] = item_data.get('importance_level', 'notable')
                    item_data['visibility_level'] = item_data.get('visibility_level', 'obvious')
                    item_data['position_type'] = None
                    item_data['positioned_at_item_id'] = None
                    item_data['has_contents'] = item_data['capacity'] > 0
                    item_data['contents_generated'] = False
                    item_data['worn_slot'] = None
                    item_data['carry_method'] = None

                    items.append(item_data)

                if not items:
                    raise ValueError("No valid obvious items generated")

                logger.info(f"Successfully generated {len(items)} obvious items for {location_name}")
                return items

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

            except Exception as e:
                logger.error(f"Error generating obvious items (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

        return []

    def generate_container_contents(
        self,
        container_name: str,
        container_description: str,
        container_capacity: int,
        location_name: str,
        location_description: str,
        container_id: UUID,
        max_items: int = 10,
        created_turn: int = 0,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate contents of a container (lazy generation when opened/examined).

        Args:
            container_name: Name of the container (e.g., "oak wardrobe")
            container_description: Description of the container
            container_capacity: Maximum capacity of container
            location_name: Name of the room (for context)
            location_description: Description of the room (for context)
            container_id: UUID of the container
            max_items: Maximum number of items to generate
            created_turn: Current turn number
            max_retries: Number of retries on invalid JSON

        Returns:
            List of item dictionaries (contained items)
        """
        system_prompt = f"""You are generating contents of a container in a dark fantasy text adventure game.

CONTAINER: {container_name}
CAPACITY: {container_capacity}
LOCATION CONTEXT: {location_name}

IMPORTANT RULES:
- Generate {max_items} or fewer items that would fit in this container
- Total SIZE of all items MUST NOT exceed container capacity ({container_capacity})
- Individual item size MUST be less than container capacity
- Items should be appropriate for this type of container and location
- Mark importance: "crucial" for plot items, "mundane" for most contents, "trivial" for junk
- Visibility level should be "hidden" (not visible until container opened)

SIZE, WEIGHT, CAPACITY scales same as before.

Return JSON array:
[
  {{
    "item_type": "furniture|clothing|weapon|tool|decoration|container|consumable|other",
    "item_name": "Display name",
    "item_description": "Detailed description (2-3 sentences)",
    "item_description_short": "Brief one-sentence description",
    "size": <number 1-{container_capacity}>,
    "weight": <number 1-10000>,
    "capacity": <number 0-capacity_limit>,
    "importance_level": "crucial|mundane|trivial",
    "visibility_level": "hidden"
  }}
]

CRITICAL:
- Total size of ALL items ≤ {container_capacity}
- Capacity MUST be ≤ 80% of size
- Return ONLY valid JSON"""

        user_prompt = f"""CONTAINER: {container_name}
CONTAINER DESCRIPTION: {container_description}
ROOM: {location_name}

Generate {max_items} or fewer items that would be found inside this container. Be realistic - items should fit within the container's capacity ({container_capacity}). Consider what would logically be stored in this type of container in this location."""

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying container contents generation (attempt {attempt + 1}/{max_retries + 1})")

                logger.info(f"Generating contents for container: {container_name}")
                response = self.llm_provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=2048
                )

                # Parse JSON
                json_str = response.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                items_data = json.loads(json_str)

                if not isinstance(items_data, list):
                    raise ValueError("Response is not a JSON array")

                # Validate and enrich items
                items = []
                total_size = 0

                for idx, item_data in enumerate(items_data):
                    required = ['item_type', 'item_name', 'item_description', 'item_description_short', 'size', 'weight', 'capacity']
                    missing = [f for f in required if f not in item_data]
                    if missing:
                        logger.warning(f"Container item {idx} missing fields: {missing}, skipping")
                        continue

                    # Validate size fits in container
                    if item_data['size'] > container_capacity:
                        logger.warning(f"Item {idx} ({item_data['item_name']}) size ({item_data['size']}) exceeds container capacity ({container_capacity}), skipping")
                        continue

                    # Check total size doesn't exceed capacity
                    if total_size + item_data['size'] > container_capacity:
                        logger.warning(f"Item {idx} would exceed container capacity, stopping generation")
                        break

                    # Validate ranges
                    if not (1 <= item_data['size'] <= 10000):
                        item_data['size'] = max(1, min(10000, item_data['size']))

                    if not (1 <= item_data['weight'] <= 10000):
                        item_data['weight'] = max(1, min(10000, item_data['weight']))

                    # Validate capacity
                    max_item_capacity = int(item_data['size'] * 0.8)
                    if item_data['capacity'] > max_item_capacity:
                        item_data['capacity'] = max_item_capacity

                    if item_data['capacity'] < 0:
                        item_data['capacity'] = 0

                    # Add metadata
                    item_data['item_id'] = uuid4()
                    item_data['location_id'] = None  # Contained items have no location_id
                    item_data['created_turn'] = created_turn
                    item_data['contained_by_item_id'] = container_id  # CONTAINED
                    item_data['carried_by_character_id'] = None
                    item_data['current_state'] = None

                    # Set hybrid fields
                    item_data['importance_level'] = item_data.get('importance_level', 'mundane')
                    item_data['visibility_level'] = item_data.get('visibility_level', 'hidden')
                    item_data['position_type'] = None
                    item_data['positioned_at_item_id'] = None
                    item_data['has_contents'] = item_data['capacity'] > 0
                    item_data['contents_generated'] = False
                    item_data['worn_slot'] = None
                    item_data['carry_method'] = None

                    items.append(item_data)
                    total_size += item_data['size']

                if not items:
                    logger.info(f"No items generated for container {container_name} (may be empty)")
                    return []

                logger.info(f"Successfully generated {len(items)} items for container {container_name} (total size: {total_size}/{container_capacity})")
                return items

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

            except Exception as e:
                logger.error(f"Error generating container contents (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

        return []

    def generate_searchable_items(
        self,
        location_name: str,
        location_description: str,
        location_id: int,
        max_items: int = 5,
        created_turn: int = 0,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate hidden items found via search action.

        These are items that weren't obvious on first glance but can be
        discovered through thorough investigation.

        Args:
            location_name: Name of the location
            location_description: Detailed description of the location
            location_id: Database location ID
            max_items: Maximum number of items to generate (default 5)
            created_turn: Turn number when items were created
            max_retries: Number of retries on invalid JSON

        Returns:
            List of hidden item dictionaries
        """
        system_prompt = f"""You are generating HIDDEN or SEARCHABLE items for a dark fantasy text adventure game.

IMPORTANT:
- Generate ONLY {max_items} items maximum
- These are items NOT obvious at first glance
- Items found through careful searching, investigation, or examination
- Mark visibility as "hidden" (not visible until searched)
- Mark importance: "crucial" for plot items, "notable" for valuable items, "mundane" or "trivial" for common finds

Examples of searchable items:
- Hidden compartments, secret drawers
- Items under furniture, behind curtains
- Small objects in corners, cracks, shadows
- Items in less obvious places (under beds, behind paintings)
- Documents, notes, keys in unexpected places

SIZE, WEIGHT, CAPACITY scales same as before.

Return JSON array:
[
  {{
    "item_type": "furniture|clothing|weapon|tool|decoration|container|consumable|other",
    "item_name": "Display name",
    "item_description": "Detailed description (2-3 sentences)",
    "item_description_short": "Brief one-sentence description",
    "size": <number 1-10000>,
    "weight": <number 1-10000>,
    "capacity": <number 0-capacity_limit>,
    "importance_level": "crucial|notable|mundane|trivial",
    "visibility_level": "hidden"
  }}
]

CRITICAL:
- Capacity MUST be ≤ 80% of size
- Return ONLY valid JSON
- Maximum {max_items} items"""

        user_prompt = f"""LOCATION: {location_name}

DESCRIPTION:
{location_description}

A character is searching this location carefully. Generate {max_items} or fewer HIDDEN items that would be discovered through thorough investigation. These should be things not immediately obvious."""

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying searchable items generation (attempt {attempt + 1}/{max_retries + 1})")

                logger.info(f"Generating searchable items for location: {location_name}")
                response = self.llm_provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.8,  # Higher creativity for hidden items
                    max_tokens=2048
                )

                # Parse JSON
                json_str = response.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                items_data = json.loads(json_str)

                if not isinstance(items_data, list):
                    raise ValueError("Response is not a JSON array")

                # Validate and enrich items
                items = []
                for idx, item_data in enumerate(items_data):
                    required = ['item_type', 'item_name', 'item_description', 'item_description_short', 'size', 'weight', 'capacity']
                    missing = [f for f in required if f not in item_data]
                    if missing:
                        logger.warning(f"Searchable item {idx} missing fields: {missing}, skipping")
                        continue

                    # Validate ranges
                    if not (1 <= item_data['size'] <= 10000):
                        item_data['size'] = max(1, min(10000, item_data['size']))

                    if not (1 <= item_data['weight'] <= 10000):
                        item_data['weight'] = max(1, min(10000, item_data['weight']))

                    # Validate capacity
                    max_capacity = int(item_data['size'] * 0.8)
                    if item_data['capacity'] > max_capacity:
                        item_data['capacity'] = max_capacity

                    if item_data['capacity'] < 0:
                        item_data['capacity'] = 0

                    # Add metadata
                    item_data['item_id'] = uuid4()
                    item_data['location_id'] = location_id
                    item_data['created_turn'] = created_turn
                    item_data['contained_by_item_id'] = None
                    item_data['carried_by_character_id'] = None
                    item_data['current_state'] = None

                    # Ensure importance/visibility are set
                    item_data['importance_level'] = item_data.get('importance_level', 'mundane')
                    item_data['visibility_level'] = 'hidden'  # Always hidden
                    item_data['position_type'] = None
                    item_data['positioned_at_item_id'] = None
                    item_data['has_contents'] = item_data['capacity'] > 0
                    item_data['contents_generated'] = False
                    item_data['worn_slot'] = None
                    item_data['carry_method'] = None

                    items.append(item_data)

                if not items:
                    logger.info(f"No searchable items generated for {location_name} (location may be thoroughly explored)")
                    return []

                logger.info(f"Successfully generated {len(items)} searchable items for {location_name}")
                return items

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

            except Exception as e:
                logger.error(f"Error generating searchable items (attempt {attempt + 1}): {e}")
                if attempt >= max_retries:
                    logger.error("Max retries reached, returning empty list")
                    return []

        return []
