"""
Item Action Parser - Extract and apply item state changes from action outcomes

Parses action descriptions to detect item manipulations and updates Qdrant accordingly.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class ItemActionParser:
    """Parse action outcomes for item state changes."""

    def __init__(self, item_store, llm_provider=None):
        """
        Initialize parser.

        Args:
            item_store: ItemStore instance for querying/updating items
            llm_provider: Optional LLM for complex parsing (fallback to regex)
        """
        self.item_store = item_store
        self.llm_provider = llm_provider

    def extract_item_manipulations(
        self,
        action_outcome: str,
        character_id: UUID,
        location_id: int
    ) -> List[Dict[str, Any]]:
        """
        Extract item manipulations from action outcome text.

        Detects:
        - Pick up / take / grab
        - Put down / drop / place
        - Wear / don / put on
        - Remove / take off
        - Move / position
        - Damage / break / destroy
        - Open / close (containers)

        Args:
            action_outcome: Text description of what happened
            character_id: Character performing action
            location_id: Current location

        Returns:
            List of detected changes: [{
                'action_type': 'pick_up'|'put_down'|'wear'|'remove'|'move'|'damage'|'open',
                'item_name': str,
                'target_item_name': Optional[str],  # For "place X on Y"
                'position_type': Optional[str],  # on, in, under, beside
                'damage_description': Optional[str],
                'new_state': Optional[str]
            }]
        """
        changes = []

        # Pattern matching for common item manipulations
        patterns = [
            # Pick up / take
            (r'(picks? up|takes?|grabs?|grasps?|seizes?)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\s+from|\s+off|\.|,|$)', 'pick_up'),

            # Put down / drop
            (r'(puts? down|drops?|releases?|sets? down)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\s+on|\s+in|\s+beside|\.|,|$)', 'put_down'),

            # Place on/in
            (r'(places?|sets?|puts?)\s+(?:the\s+)?([a-zA-Z\s]+?)\s+(on|in|under|beside|behind)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|,|$)', 'place'),

            # Wear / don
            (r'(wears?|dons?|puts? on)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|,|$)', 'wear'),

            # Remove / take off
            (r'(removes?|takes? off|doffs?)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|,|$)', 'remove'),

            # Damage / break
            (r'(damages?|breaks?|shatters?|tears?|rips?)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|,|$)', 'damage'),

            # Open / close
            (r'(opens?|closes?)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|,|$)', 'open_close'),

            # Search / examine (for generating hidden items)
            (r'(searches?|examines? carefully|investigates?|looks? around|looks? for)\s+(?:the\s+)?(?:room|area|location|surroundings?)?(?:\.|,|$)', 'search_location'),
        ]

        for pattern, action_type in patterns:
            matches = re.finditer(pattern, action_outcome, re.IGNORECASE)
            for match in matches:
                if action_type == 'place':
                    # Special handling for "place X on Y"
                    changes.append({
                        'action_type': 'place',
                        'item_name': match.group(2).strip(),
                        'position_type': match.group(3).strip(),
                        'target_item_name': match.group(4).strip()
                    })
                elif action_type == 'damage':
                    changes.append({
                        'action_type': 'damage',
                        'item_name': match.group(2).strip(),
                        'damage_description': f"{match.group(1)} by {character_id}"
                    })
                elif action_type == 'open_close':
                    changes.append({
                        'action_type': 'open' if 'open' in match.group(1).lower() else 'close',
                        'item_name': match.group(2).strip()
                    })
                elif action_type == 'search_location':
                    # Special handling for location search (no specific item)
                    changes.append({
                        'action_type': 'search_location'
                    })
                else:
                    changes.append({
                        'action_type': action_type,
                        'item_name': match.group(2).strip()
                    })

        logger.debug(f"Extracted {len(changes)} item manipulations from action")
        return changes

    def apply_item_changes(
        self,
        changes: List[Dict[str, Any]],
        character_id: UUID,
        location_id: int,
        current_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Apply detected item changes to Qdrant.

        Args:
            changes: List of changes from extract_item_manipulations
            character_id: Character performing actions
            location_id: Current location
            current_turn: Current turn number

        Returns:
            List of successfully applied changes with item IDs
        """
        applied = []

        for change in changes:
            try:
                action_type = change['action_type']

                # Handle search_location action (no specific item)
                if action_type == 'search_location':
                    # Flag that hidden items should be generated
                    applied.append({
                        'action_type': 'search_location',
                        'location_id': location_id,
                        'needs_searchable_items_generation': True
                    })
                    continue

                # Get item name (required for all other actions)
                item_name = change.get('item_name')
                if not item_name:
                    logger.warning(f"No item_name provided for action {action_type}")
                    continue

                # Find the item
                item = self.item_store.find_item_by_name(
                    item_name=item_name,
                    location_id=location_id
                )

                if not item:
                    logger.warning(f"Item '{item_name}' not found at location {location_id}")
                    continue

                item_id = UUID(item['item_id'])

                # Apply change based on type
                if action_type == 'pick_up':
                    success = self.item_store.update_item(
                        item_id=item_id,
                        carried_by_character_id=str(character_id),
                        location_id=None,  # No longer at location
                        positioned_at_item_id=None,
                        position_type=None,
                        carry_method='carried'
                    )
                    if success:
                        applied.append({**change, 'item_id': str(item_id)})

                elif action_type == 'put_down':
                    success = self.item_store.update_item(
                        item_id=item_id,
                        carried_by_character_id=None,
                        location_id=location_id,
                        carry_method=None
                    )
                    if success:
                        applied.append({**change, 'item_id': str(item_id)})

                elif action_type == 'place':
                    # Place item on/in/beside another item
                    target_item = self.item_store.find_item_by_name(
                        item_name=change['target_item_name'],
                        location_id=location_id
                    )

                    if target_item:
                        target_id = UUID(target_item['item_id'])
                        position_type = change['position_type']

                        # If placing "in" container, check capacity
                        if position_type == 'in':
                            if not self.item_store.can_fit_in_container(item['size'], target_id):
                                logger.warning(f"Item '{item_name}' cannot fit in '{change['target_item_name']}'")
                                continue

                            success = self.item_store.update_item(
                                item_id=item_id,
                                contained_by_item_id=str(target_id),
                                location_id=None,
                                carried_by_character_id=None,
                                position_type=None,
                                positioned_at_item_id=None,
                                carry_method=None
                            )
                        else:
                            # Positioned "on", "under", "beside", etc.
                            success = self.item_store.update_item(
                                item_id=item_id,
                                positioned_at_item_id=str(target_id),
                                position_type=position_type,
                                location_id=location_id,
                                carried_by_character_id=None,
                                contained_by_item_id=None,
                                carry_method=None
                            )

                        if success:
                            applied.append({**change, 'item_id': str(item_id)})
                    else:
                        logger.warning(f"Target item '{change['target_item_name']}' not found")

                elif action_type == 'wear':
                    # Determine worn slot from item type
                    worn_slot = self._infer_worn_slot(item)

                    success = self.item_store.update_item(
                        item_id=item_id,
                        carried_by_character_id=str(character_id),
                        location_id=None,
                        carry_method='worn',
                        worn_slot=worn_slot,
                        positioned_at_item_id=None,
                        position_type=None
                    )
                    if success:
                        applied.append({**change, 'item_id': str(item_id), 'worn_slot': worn_slot})

                elif action_type == 'remove':
                    # Remove worn item (stays in inventory as "carried")
                    success = self.item_store.update_item(
                        item_id=item_id,
                        carry_method='carried',
                        worn_slot=None
                    )
                    if success:
                        applied.append({**change, 'item_id': str(item_id)})

                elif action_type == 'damage':
                    # Update item state to reflect damage
                    current_state = item.get('current_state', '')
                    new_state = f"{current_state}; {change['damage_description']}".strip('; ')

                    success = self.item_store.update_item(
                        item_id=item_id,
                        current_state=new_state
                    )
                    if success:
                        applied.append({**change, 'item_id': str(item_id)})

                elif action_type == 'open':
                    # Mark container as opened, potentially generate contents
                    if item.get('has_contents') and not item.get('contents_generated'):
                        logger.info(f"Container '{item_name}' opened - contents should be generated")
                        # Flag for lazy generation (caller should handle)
                        applied.append({
                            **change,
                            'item_id': str(item_id),
                            'needs_contents_generation': True
                        })
                    else:
                        applied.append({**change, 'item_id': str(item_id)})

            except Exception as e:
                logger.error(f"Error applying change {change}: {e}")
                continue

        logger.info(f"Applied {len(applied)}/{len(changes)} item changes")
        return applied

    def _infer_worn_slot(self, item: Dict[str, Any]) -> str:
        """
        Infer body slot from item type and name.

        Returns: head, torso, legs, feet, hands, neck, finger, waist, back
        """
        item_name = item['item_name'].lower()
        item_type = item.get('item_type', '').lower()

        # Check name keywords
        if any(word in item_name for word in ['helmet', 'hat', 'crown', 'hood', 'cap']):
            return 'head'
        elif any(word in item_name for word in ['shirt', 'tunic', 'robe', 'vest', 'armor', 'dress', 'gown']):
            return 'torso'
        elif any(word in item_name for word in ['pants', 'trousers', 'leggings', 'skirt']):
            return 'legs'
        elif any(word in item_name for word in ['boots', 'shoes', 'sandals', 'slippers']):
            return 'feet'
        elif any(word in item_name for word in ['gloves', 'gauntlets', 'mittens']):
            return 'hands'
        elif any(word in item_name for word in ['necklace', 'pendant', 'amulet', 'collar']):
            return 'neck'
        elif any(word in item_name for word in ['ring', 'band']):
            return 'finger'
        elif any(word in item_name for word in ['belt', 'sash', 'girdle']):
            return 'waist'
        elif any(word in item_name for word in ['cloak', 'cape', 'mantle']):
            return 'back'

        # Fallback to item type
        if item_type == 'clothing':
            return 'torso'  # Default clothing slot

        return 'torso'  # Ultimate fallback

    def parse_and_apply(
        self,
        action_outcome: str,
        character_id: UUID,
        location_id: int,
        current_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Convenience method: extract and apply in one call.

        Args:
            action_outcome: Action description text
            character_id: Character performing action
            location_id: Current location
            current_turn: Current turn number

        Returns:
            List of applied changes with item IDs
        """
        changes = self.extract_item_manipulations(
            action_outcome=action_outcome,
            character_id=character_id,
            location_id=location_id
        )

        if not changes:
            return []

        applied = self.apply_item_changes(
            changes=changes,
            character_id=character_id,
            location_id=location_id,
            current_turn=current_turn
        )

        return applied
