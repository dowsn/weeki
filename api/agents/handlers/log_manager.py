from api.agents.models.conversation_models import ConversationState, LogState
from typing import List
from api.agents.handlers.pinecone_manager import PineconeManager
from channels.db import database_sync_to_async
from app.models import SessionLog, Topic
import numpy as np


class LogManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.pinecone_manager = pinecone_manager

  async def check_logs(self, state: ConversationState) -> ConversationState:
    matched_logs = []

    # First check cached logs if embedding is available
    if state.embedding is not None and hasattr(state, 'cached_logs'):
      matched_logs = self._compare_cached_logs(state.cached_logs,
                                               state.embedding)

    # If no matches in cache, query Pinecone
    if len(matched_logs) == 0 and state.embedding:
      new_logs = await self.pinecone_manager.retrieve_logs(
          embedding=state.embedding)

      # Add new logs to cache for future reference
      if hasattr(state, 'cached_logs'):
        state.cached_logs.extend(new_logs)
      else:
        state.cached_logs = new_logs

      matched_logs = new_logs

    # Set current logs to matched logs
    state.current_logs = matched_logs
    return state

  def _compare_cached_logs(self, cached_logs: List[LogState],
                           context_embedding: List[float]) -> List[LogState]:
    # Similar to topic comparison but for logs
    matched = []
    similarity_threshold = 0.7  # You may want to adjust this

    for log in cached_logs:
      if log.embedding is not None:
        similarity = self._cosine_similarity(context_embedding, log.embedding)
        if similarity > similarity_threshold:
          matched.append(log)

    return matched

  def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

  async def get_session_logs(self,
                             session_id: int,
                             status: int = 0) -> List[LogState]:
    """Get logs for a specific session with optional status filtering"""
    query = {'session_id': session_id}
    if status is not None:
      query['status'] = status

    @database_sync_to_async
    def fetch_session_logs():
      return list(SessionLog.objects.filter(**query).select_related('log'))

    session_logs = await fetch_session_logs()

    # Convert to LogState objects
    log_states = []
    for sl in session_logs:
      log = sl.log

      @database_sync_to_async
      def get_topic():
        return Topic.objects.get(id=log.topic_id)

      topic = await get_topic()

      # add
      embedding = await self.pinecone_manager.get_topic_vector_by_id(
          topic_id=int(topic.pk))

      log_states.append(
          LogState(topic_id=log.topic_id,
                   topic_name=topic.name,
                   text=log.text,
                   embedding=embedding,
                   chat_session_id=session_id))

    return log_states
