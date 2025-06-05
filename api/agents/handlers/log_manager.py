from typing import List
from api.agents.handlers.pinecone_manager import PineconeManager
from channels.db import database_sync_to_async
from app.models import SessionLog, Topic
import numpy as np
from api.agents.models.conversation_models import ConversationState, LogState


class LogManager:
  def __init__(self, pinecone_manager: PineconeManager):
      self.pinecone_manager = pinecone_manager

  async def check_logs(self, state: ConversationState) -> ConversationState:
      state.current_logs = []
      matched_logs = []

      if state.embedding:
          print("Searching for logs with time-boosted scoring")

          # Use the same parameters as topics for consistency
          new_logs = await self.pinecone_manager.retrieve_logs(
              embedding=state.embedding,
              base_threshold=0.4,      # Must be semantically relevant
              final_threshold=0.5,     # Must pass final quality check
              max_results=3)           # Maximum 3 logs (same as topics)
          matched_logs = new_logs

      state.current_logs = matched_logs
      print(f"Matched logs: {len(matched_logs)}")
      for log in matched_logs:
          print(f"  - {log.topic_name} (confidence: {log.confidence:.3f})")

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

          # Get embedding from pinecone (you might want to get log embedding instead of topic embedding)
          embedding = await self.pinecone_manager.get_topic_vector_by_id(
              topic_id=int(topic.pk))

          log_states.append(
              LogState(topic_id=log.topic_id,
                      topic_name=topic.name,
                      text=log.text,
                      embedding=embedding,
                      chat_session_id=session_id,
                      confidence=1.0))  # Add confidence field if needed

      return log_states