from app.models import Topic, Log, Chat_Session, Message
from django.db import transaction
from datetime import date
from .graph_model import TopicState

class TopicDBManager:
    """Handles interaction between agent state and Django Topic model"""

    @staticmethod
    async def create_topic_from_state(topic_state: TopicState, user_id: int) -> Topic:
        """Creates a new Topic in the database from a TopicState"""
        topic = await Topic.objects.acreate(
            name=topic_state.name,
            description=topic_state.description,
            user_id=user_id,
            active=topic_state.active
        )
        return topic

    @staticmethod
    async def update_topic_description(topic_id: int, new_description: str) -> None:
        """Updates topic description and creates PastTopics entry"""
        topic = await Topic.objects.aget(id=topic_id)

        # Create past topic record
        await PastTopics.objects.acreate(
            topic=topic,
            description=topic.description,
            title=topic.name
        )

        # Update current topic
        topic.description = new_description
        await topic.asave()

    @staticmethod
    async def create_log_entry(user_id: int, chat_session_id: int, topic_id: int, text: str) -> None:
        """Creates a new Log entry"""
        await Log.objects.acreate(
            user_id=user_id,
            chat_session_id=chat_session_id,
            topic_id=topic_id,
            date=date.today(),
            text=text
        )

class StateManager:
    """Manages conversion between Django models and Pydantic state objects"""

    @staticmethod
    def topic_to_state(topic: Topic) -> TopicState:
        """Converts Django Topic to TopicState"""
        return TopicState(
            id=topic.id,
            name=topic.name,
            description=topic.description,
            active=topic.active,
            date_updated=topic.date_updated
        )

    @staticmethod
    def state_to_topic_dict(state: TopicState) -> dict:
        """Converts TopicState to dict for Django model creation/update"""
        return {
            'name': state.name,
            'description': state.description,
            'active': state.active
        }