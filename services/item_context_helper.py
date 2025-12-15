"""
Item Context Helper - Prepare items for LLM context

Retrieves and formats items for inclusion in LLM prompts.
Focuses on relevant items only to manage token budget.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class ItemContextHelper:
    """Helper for preparing item context for LLM prompts."""

    def __init__(self, item_store):
        """
        Initialize helper.

        Args:
            item_store: ItemStore instance
        """
        self.item_store = item_store

    def get_relevant_items_for_context(
        self,
        location_id: int,
        action_description: Optional[str],
        character_id: UUID,
        max_items: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve only relevant items for LLM context.

        This is token-efficient: instead of loading all 50 items in a room,
        only load items that are:
        1. Obvious/visible in the room
        2. Semantically relevant to the action
        3. In the character's inventory

        Args:
            location_id: Current location
            action_description: Action being taken (for semantic search)
            character_id: Character performing action
            max_items: Maximum items to return

        Returns:
            List of item dictionaries (deduplicated and prioritized)
        """
        try:
            all_items = []
            seen_ids = set()

            # 1. Get character's inventory (highest priority)
            inventory = self.item_store.get_items_carried_by(character_id)
            for item in inventory[:5]:  # Limit to 5 inventory items
                item_id = item['item_id']
                if item_id not in seen_ids:
                    all_items.append(item)
                    seen_ids.add(item_id)

            # 2. Get obvious items in room (always visible)
            obvious_items = self.item_store.search_items(
                location_id=location_id,
                visibility_levels=["obvious", "visible"],
                limit=5
            )
            for item in obvious_items:
                item_id = item['item_id']
                if item_id not in seen_ids:
                    all_items.append(item)
                    seen_ids.add(item_id)

            # 3. Semantic search for action-relevant items (if action provided)
            if action_description:
                action_relevant = self.item_store.semantic_search(
                    query_text=action_description,
                    location_id=location_id,
                    limit=3,
                    score_threshold=0.7
                )
                for item in action_relevant:
                    item_id = item['item_id']
                    if item_id not in seen_ids:
                        all_items.append(item)
                        seen_ids.add(item_id)

            # Return limited set
            result = all_items[:max_items]
            logger.debug(f"Retrieved {len(result)} relevant items for context")
            return result

        except Exception as e:
            logger.error(f"Error getting relevant items: {e}")
            return []

    def get_item_position_description(self, item: Dict[str, Any]) -> str:
        """
        Get narrative description of where item is positioned.

        Examples:
        - "on the mahogany table"
        - "in the oak wardrobe"
        - "in the room"

        Args:
            item: Item dictionary

        Returns:
            Position description string
        """
        try:
            # Check if positioned relative to another item (spatial positioning)
            if item.get('position_type') and item.get('positioned_at_item_id'):
                positioned_at = self.item_store.get_item(
                    UUID(item['positioned_at_item_id'])
                )
                if positioned_at:
                    return f"{item['position_type']} the {positioned_at['item_name']}"

            # Check if contained within another item
            if item.get('contained_by_item_id'):
                container = self.item_store.get_item(
                    UUID(item['contained_by_item_id'])
                )
                if container:
                    return f"in the {container['item_name']}"

            # Check if carried/worn by character
            if item.get('carried_by_character_id'):
                carry_method = item.get('carry_method', 'carried')
                if carry_method == 'worn':
                    worn_slot = item.get('worn_slot', 'body')
                    return f"worn on {worn_slot}"
                elif carry_method == 'wielded':
                    return "wielded"
                else:
                    return "carried"

            # Default: in the room
            return "in the room"

        except Exception as e:
            logger.error(f"Error getting position description: {e}")
            return "in the room"

    def format_items_for_prompt(
        self,
        items: List[Dict[str, Any]],
        include_details: bool = True
    ) -> str:
        """
        Format items as text for LLM prompt.

        Args:
            items: List of item dictionaries
            include_details: Whether to include full descriptions

        Returns:
            Formatted string for prompt
        """
        if not items:
            return "No notable items are visible."

        lines = []

        for item in items:
            name = item['item_name']
            position = self.get_item_position_description(item)

            if include_details:
                # Include short description
                desc_short = item.get('item_description_short', '')

                # Include state if modified
                state = item.get('current_state')
                state_text = f" ({state})" if state else ""

                lines.append(f"- {name}: {desc_short} [{position}]{state_text}")
            else:
                # Brief listing
                lines.append(f"- {name} [{position}]")

        return "\n".join(lines)

    def format_inventory_for_prompt(
        self,
        character_id: UUID,
        include_details: bool = True
    ) -> str:
        """
        Format character's inventory as text for prompt.

        Separates worn items from carried items.

        Args:
            character_id: Character UUID
            include_details: Whether to include descriptions

        Returns:
            Formatted inventory string
        """
        try:
            # Get worn items
            worn_items = self.item_store.get_worn_items(character_id)

            # Get carried items (not worn)
            carried_items = self.item_store.get_carried_items_not_worn(character_id)

            # Calculate total weight
            total_weight = self.item_store.get_total_carried_weight(character_id)

            lines = []

            if worn_items:
                lines.append("WEARING:")
                for item in worn_items:
                    name = item['item_name']
                    worn_slot = item.get('worn_slot', 'body')

                    if include_details:
                        desc_short = item.get('item_description_short', '')
                        lines.append(f"  - {name} (on {worn_slot}): {desc_short}")
                    else:
                        lines.append(f"  - {name} (on {worn_slot})")

            if carried_items:
                lines.append("CARRYING:")
                for item in carried_items:
                    name = item['item_name']

                    if include_details:
                        desc_short = item.get('item_description_short', '')
                        lines.append(f"  - {name}: {desc_short}")
                    else:
                        lines.append(f"  - {name}")

            if not worn_items and not carried_items:
                lines.append("(Empty-handed)")

            lines.append(f"\nTotal carried weight: {total_weight}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error formatting inventory: {e}")
            return "(Unable to retrieve inventory)"

    def get_container_contents_summary(
        self,
        container_id: UUID,
        max_items: int = 5
    ) -> str:
        """
        Get a brief summary of what's in a container.

        Args:
            container_id: Container UUID
            max_items: Maximum items to list

        Returns:
            Summary string
        """
        try:
            container = self.item_store.get_item(container_id)
            if not container:
                return "Container not found."

            # Check if contents have been generated
            if container.get('has_contents') and not container.get('contents_generated'):
                return f"The {container['item_name']} has not been opened yet."

            # Get contents
            contents = self.item_store.get_items_in_container(container_id)

            if not contents:
                return f"The {container['item_name']} is empty."

            # List items
            item_names = [item['item_name'] for item in contents[:max_items]]

            if len(contents) > max_items:
                return f"The {container['item_name']} contains: {', '.join(item_names)}, and {len(contents) - max_items} more items."
            else:
                return f"The {container['item_name']} contains: {', '.join(item_names)}."

        except Exception as e:
            logger.error(f"Error getting container summary: {e}")
            return "Unable to inspect container."

    def get_clothing_description_from_items(
        self,
        character_id: UUID,
        brief: bool = False
    ) -> Optional[str]:
        """
        Generate dynamic clothing description from worn items in Qdrant.

        Args:
            character_id: Character UUID
            brief: If True, return very brief description (item names only)

        Returns:
            Clothing description string or None if no items worn
        """
        try:
            # Get worn items from Qdrant
            worn_items = self.item_store.get_worn_items(character_id)

            if not worn_items:
                return None

            if brief:
                # Brief: just list item names
                item_names = [item['item_name'] for item in worn_items]
                return ", ".join(item_names)
            else:
                # Detailed: include short descriptions
                descriptions = []
                for item in worn_items:
                    name = item['item_name']
                    desc_short = item.get('item_description_short', '')
                    worn_slot = item.get('worn_slot', 'body')

                    # Include current_state if modified
                    state = item.get('current_state')
                    state_text = f" ({state})" if state else ""

                    descriptions.append(f"{name} (on {worn_slot}): {desc_short}{state_text}")

                return "; ".join(descriptions)

        except Exception as e:
            logger.error(f"Error generating clothing description: {e}")
            return None

    def apply_item_changes_from_atmospheric_description(
        self,
        atmospheric_data: Dict[str, Any],
        location_id: int,
        character_id: Optional[UUID] = None
    ) -> int:
        """
        Parse atmospheric description and apply item state changes.

        This method processes LLM-generated atmospheric descriptions and
        updates items in Qdrant based on described changes.

        Args:
            atmospheric_data: Dict containing atmospheric description and item changes
            location_id: Current location ID
            character_id: Optional character ID if changes are character-specific

        Returns:
            Number of items updated

        Expected atmospheric_data structure:
        {
            "description": "narrative description...",
            "mood_deltas": {...},
            "item_changes": [
                {
                    "item_name": "candle",
                    "visibility_level": "obvious",  # optional
                    "current_state": "flickering dimly",  # optional
                    "position_type": "on",  # optional
                    "positioned_at": "wooden table"  # optional (item name)
                }
            ]
        }
        """
        try:
            item_changes = atmospheric_data.get('item_changes', [])
            if not item_changes:
                logger.debug("No item changes in atmospheric data")
                return 0

            updated_count = 0

            for change in item_changes:
                item_name = change.get('item_name')
                if not item_name:
                    continue

                # Find the item (search in location or character inventory)
                item = None
                if character_id:
                    # Search in character's inventory first
                    inventory = self.item_store.get_items_carried_by(character_id)
                    item = next((i for i in inventory if i['item_name'].lower() == item_name.lower()), None)

                if not item:
                    # Search in location
                    item = self.item_store.find_item_by_name(item_name, location_id)

                if not item:
                    logger.warning(f"Item '{item_name}' not found for update")
                    continue

                # Prepare update fields
                update_fields = {}

                if 'visibility_level' in change:
                    update_fields['visibility_level'] = change['visibility_level']

                if 'current_state' in change:
                    update_fields['current_state'] = change['current_state']

                if 'position_type' in change:
                    update_fields['position_type'] = change['position_type']

                # Handle positioned_at (need to find item ID from name)
                if 'positioned_at' in change:
                    positioned_at_name = change['positioned_at']
                    positioned_at_item = self.item_store.find_item_by_name(positioned_at_name, location_id)
                    if positioned_at_item:
                        update_fields['positioned_at_item_id'] = positioned_at_item['item_id']

                # Apply updates
                if update_fields:
                    item_id = UUID(item['item_id'])
                    success = self.item_store.update_item(item_id, **update_fields)
                    if success:
                        updated_count += 1
                        logger.info(f"Updated item '{item_name}': {update_fields}")

            logger.info(f"Applied {updated_count} item changes from atmospheric description")
            return updated_count

        except Exception as e:
            logger.error(f"Error applying item changes from atmospheric description: {e}")
            import traceback
            traceback.print_exc()
            return 0
