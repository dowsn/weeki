from api.agents.models.conversation_models import ConversationState, TopicState
from typing import List
from api.agents.handlers.pinecone_manager import PineconeManager


class LogManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.pinecone_manager = pinecone_manager

  # where is this called
  async def check_logs(self, state: ConversationState) -> ConversationState:
    # Early return if thresholds not met

    new_logs = await self.pinecone_manager.retrieve_logs(
        embedding=state.embedding, user_id=state.user_id)

    state.current_logs = new_logs

    # Filter by confidence
    return state
