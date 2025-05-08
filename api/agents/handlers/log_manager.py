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
    state.current_logs = []
    print("checking logs")

    # If no matches in cache, query Pinecone
    if len(matched_logs) == 0 and state.embedding:
      new_logs = await self.pinecone_manager.retrieve_logs(
          embedding=state.embedding)

      matched_logs = new_logs

    # Set current logs to matched logs 
    state.current_logs = matched_logs
    return state

  

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
