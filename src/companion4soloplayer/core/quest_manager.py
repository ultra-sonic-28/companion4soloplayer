"""
Quest management module.
Handles quest tracking and objectives.
"""

from enum import Enum

from pydantic import BaseModel, Field


class QuestStatus(Enum):
    """Quest status enumeration."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Objective(BaseModel):
    """Quest objective."""
    description: str = Field(..., description="Objective description")
    completed: bool = Field(default=False, description="Completion status")


class Quest(BaseModel):
    """Quest representation."""
    name: str = Field(..., description="Quest name")
    description: str = Field(..., description="Quest description")
    objectives: list[Objective] = Field(default_factory=list, description="Quest objectives")
    status: QuestStatus = Field(default=QuestStatus.NOT_STARTED, description="Quest status")
    rewards: dict[str, int] = Field(default_factory=dict, description="Quest rewards")


class QuestManager:
    """Manages quests and their progression."""

    def __init__(self) -> None:
        """Initialize the quest manager."""
        self.quests: dict[str, Quest] = {}
        self.active_quest: str | None = None

    def create_quest(
        self,
        name: str,
        description: str,
        objectives: list[str]
    ) -> Quest:
        """Create a new quest.

        Args:
            name: Quest name
            description: Quest description
            objectives: List of objective descriptions

        Returns:
            The created Quest object

        Raises:
            ValueError: If quest name already exists
        """
        if name in self.quests:
            raise ValueError(f"Quest '{name}' already exists")

        quest = Quest(
            name=name,
            description=description,
            objectives=[Objective(description=obj) for obj in objectives]
        )
        self.quests[name] = quest
        return quest

    def start_quest(self, name: str) -> bool:
        """Start a quest.

        Args:
            name: Quest name

        Returns:
            True if quest was started, False if not found
        """
        if name in self.quests:
            self.quests[name].status = QuestStatus.IN_PROGRESS
            self.active_quest = name
            return True
        return False

    def complete_objective(self, quest_name: str, objective_index: int) -> bool:
        """Mark an objective as completed.

        Args:
            quest_name: Quest name
            objective_index: Index of the objective

        Returns:
            True if objective was completed, False if invalid
        """
        if quest_name not in self.quests:
            return False

        quest = self.quests[quest_name]
        if 0 <= objective_index < len(quest.objectives):
            quest.objectives[objective_index].completed = True

            if all(obj.completed for obj in quest.objectives):
                quest.status = QuestStatus.COMPLETED

            return True
        return False

    def get_active_quest(self) -> Quest | None:
        """Get the currently active quest.

        Returns:
            Active quest or None
        """
        if self.active_quest:
            return self.quests.get(self.active_quest)
        return None
