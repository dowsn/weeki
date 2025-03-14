from api.agents.models.conversation_models import ConversationState, TopicState
from typing import List
from app.models import SessionTopic
from channels.db import database_sync_to_async

import numpy as np
from api.agents.handlers.pinecone_manager import PineconeManager
from app.models import Topic


class TopicManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.similarity_threshold = 0.7
    self.confidence_threshold = 0.5
    self.pinecone_manager = pinecone_manager

  # where is this called
  async def check_topics(self, state: ConversationState) -> ConversationState:
    matched_topics = []
    # Check cached topics
    if state.embedding is not None:
      matched_topics = self._compare_cached_topics(state.cached_topics,
                                                   state.embedding)
    # Query Pinecone if needed
    if len(matched_topics) == 0 and state.embedding:
      new_topics = await self.pinecone_manager.retrieve_topics(
          embedding=state.embedding)
      state.cached_topics.extend(new_topics)
      matched_topics = new_topics

    print(f"Matched topics: {[t.topic_name for t in matched_topics]}")
    state.current_topics = matched_topics

    if len(matched_topics) == 0:
      state = await self.create_new_topic(state)

    state.embedding = None
    return state

  async def create_new_topic(self,
                             state: ConversationState) -> ConversationState:
    state.potential_topic = "NA"
    return state

  def _compare_cached_topics(
      self, cached_topics: List[TopicState],
      context_embedding: List[float]) -> List[TopicState]:
    matched = []
    for topic in cached_topics:
      if topic.embedding is not None:
        similarity = self._cosine_similarity(context_embedding,
                                             topic.embedding)
        if similarity > self.similarity_threshold:
          topic.confidence = (topic.confidence * 0.7) + (similarity * 0.3)
          matched.append(topic)
        else:
          topic.confidence *= 0.9  # Decay confidence
    return matched

  def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

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
