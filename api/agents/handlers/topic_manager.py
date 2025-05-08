from api.agents.models.conversation_models import ConversationState, TopicState
from typing import List
from app.models import Conversation_Session, SessionTopic, Topic
from channels.db import database_sync_to_async
from llama_index.core import Settings

import numpy as np
from api.agents.handlers.pinecone_manager import PineconeManager


class TopicManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.similarity_threshold = 0.7
    self.confidence_threshold = 0.5
    self.pinecone_manager = pinecone_manager
    self.embedding_model = Settings.embed_model

  async def store_topic(self, topic: TopicState, state: ConversationState) -> TopicState:
    @database_sync_to_async
    def create_topic_in_db():
        topic_in_db = Topic.objects.create(
            name=topic.topic_name,
            description=topic.text,
            user_id=state.user_id
        )

        SessionTopic.objects.create(
            session_id=state.chat_session.id,
            topic_id=topic_in_db.pk,  # Note: use topic_in_db.pk here
            status=1,
            confidence=0.85
        )

        return topic_in_db

    topic_in_db = await create_topic_in_db()

    new_topic_state = TopicState(
        topic_id=topic_in_db.pk,
        topic_name=topic_in_db.name,
        text=topic.text,
        confidence=0.85,
        embedding=None
    )

    # Use pinecone_manager to create and store the embedding
    embedding = await self.pinecone_manager.upsert_topic(new_topic_state)
    new_topic_state.embedding = embedding

    return new_topic_state

  # where is this called
  async def check_topics(self, state: ConversationState) -> ConversationState:
    state.current_topics = []
    matched_topics = []

    if len(matched_topics) == 0 and state.embedding:
        new_topics = await self.pinecone_manager.retrieve_topics(
            embedding=state.embedding)
        matched_topics = new_topics

        @database_sync_to_async
        def process_topics():
            for topic in new_topics:
                try:
                    existing_topic = SessionTopic.objects.get(
                        session_id=state.session_id,
                        topic_id=topic.topic_id
                    )
                except SessionTopic.DoesNotExist:
                    SessionTopic.objects.create(
                        session_id=state.session_id,
                        topic_id=topic.topic_id,
                        status=1,
                        confidence=topic.confidence
                    )

        await process_topics()

    state.current_topics = matched_topics

    if len(matched_topics) == 0:
        state = await self.create_new_topic(state)

    state.embedding = None
    return state

  async def create_new_topic(self,
                             state: ConversationState) -> ConversationState:
    state.potential_topic = "NA"
    return state


  async def get_session_topics(self,
                               session_id: int,
                               status: int = None) -> List[TopicState]:
    """Get topics for a specific session with optional status filtering"""
    query = {'session_id': session_id}
    if status is not None:
      query['status'] = status

    @database_sync_to_async
    def fetch_session_topics():
      return list(SessionTopic.objects.filter(**query).select_related('topic'))

    session_topics = await fetch_session_topics()

    # Convert to TopicState objects
    topic_states = []
    for st in session_topics:
      topic = st.topic
      embedding = await self.pinecone_manager.get_topic_vector_by_id(topic.id)

      topic_states.append(
          TopicState(topic_id=topic.id,
                     topic_name=topic.name,
                     text=topic.description,
                     confidence=st.confidence,
                     embedding=embedding,
                     date_updated=topic.date_updated))

    return topic_states
