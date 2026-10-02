"""
Procedural generation module.
Generates dungeons, rooms, and encounters.
"""

import random


class ProceduralGenerator:
    """Generates procedural content for dungeons."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the generator.

        Args:
            seed: Optional random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

    def generate_room(self, room_type: str, level: int) -> dict:
        """Generate a dungeon room.

        Args:
            room_type: Type of room ('corridor', 'room', 'intersection', 'stairs')
            level: Dungeon level (1-10)

        Returns:
            Dictionary with room characteristics

        Raises:
            ValueError: If room_type is invalid or level out of range
        """
        if level < 1 or level > 10:
            raise ValueError("Level must be between 1 and 10")

        room_templates = {
            'corridor': [
                {'width': 1, 'length': 5, 'description': 'A narrow stone corridor'},
                {'width': 1, 'length': 8, 'description': 'A long, dark passage'},
                {'width': 2, 'length': 6, 'description': 'A wide hallway'},
            ],
            'room': [
                {'width': 4, 'length': 4, 'description': 'A small square chamber'},
                {'width': 5, 'length': 5, 'description': 'A medium-sized room'},
                {'width': 6, 'length': 8, 'description': 'A large hall'},
            ],
            'intersection': [
                {'width': 3, 'length': 3, 'description': 'A crossroads'},
                {'width': 4, 'length': 4, 'description': 'A four-way junction'},
            ],
            'stairs': [
                {'width': 2, 'length': 3, 'description': 'Stone stairs leading down'},
            ]
        }

        if room_type not in room_templates:
            raise ValueError(f"Invalid room type: {room_type}")

        template = random.choice(room_templates[room_type])
        difficulty_modifier = level / 10

        return {
            'type': room_type,
            'dimensions': (template['width'], template['length']),
            'description': template['description'],
            'level': level,
            'difficulty': difficulty_modifier
        }

    def generate_dungeon(self, num_rooms: int, level: int) -> list[dict]:
        """Generate a complete dungeon.

        Args:
            num_rooms: Number of rooms to generate
            level: Dungeon level (1-10)

        Returns:
            List of room dictionaries
        """
        rooms = []
        room_types = ['corridor', 'room', 'intersection', 'stairs']

        for i in range(num_rooms):
            room_type = random.choice(room_types)
            room = self.generate_room(room_type, level)
            room['id'] = i
            rooms.append(room)

        return rooms
