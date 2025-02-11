from typing import List, Dict
from langchain_pinecone import PineconeEmbeddings
import numpy as np
import os
from pydantic import SecretStr
from django.conf import settings
from api.agents.models.conversation_models import TopicState, ConversationState


class TopicManager:

  def __init__(self, user_id: int):
    self.creator = TopicCreator(user_id)
    self.validator = TopicValidator()

  async def handle_topic(self, query: str, state: ConversationState):
    # Unified topic handling logic
    pass


class TopicValidator:

  def __init__(self):
    if not hasattr(settings,
                   'PINECONE_API_KEY') or not settings.PINECONE_API_KEY:
      raise ValueError("PINECONE_API_KEY must be set in Django settings")

  def validate_topic_creation(self,
                              existing_topics: List[Dict],
                              new_content: str,
                              min_length: int = 400) -> bool:
    """Prevent redundant topic creation by comparing embeddings similarity"""
    # Basic validation checks

    # check at the beginning conversation by quering sql and when yes update conversation status?!!
    if len(existing_topics) < 3:
      return True
    #

    if len(new_content) < min_length:
      return False

    # Get existing descriptions
    existing_descs = [t['description'] for t in existing_topics]

    # Generate embeddings
    new_embed = self.model.embed_query(new_content)
    existing_embeds = self.model.embed_documents(existing_descs)

    # Calculate similarities using numpy
    similarities = np.dot(existing_embeds, new_embed)
    return float(np.max(similarities)) < 0.65


class TopicCreator:

  def __init__(self, user_id: int):
    self.user_id = user_id
    self.min_desc_length = 120
    self.max_desc_length = 500
    self.validator = TopicValidator()

  def create_from_analysis(self, topic_data: Dict) -> TopicState:
    """Create TopicState from analysis data"""
    from .graph_model import TopicState  # Import here to avoid circular import

    return TopicState(
        name=topic_data.get('name', '').replace('Draft: ', ''),
        description=topic_data.get('description', ''),
        actuality=1.0  # New topics start with full actuality
    )

  def _validate_length(self, topic: Dict) -> bool:
    """Validate topic description length"""
    desc_len = len(topic['description'])
    return self.min_desc_length <= desc_len <= self.max_desc_length

  async def create_interactively(self, messages: List[str]) -> Dict:
    """Guided topic creation flow"""
    detected = self._detect_potential_topic(messages)
    if not self._validate_length(detected):
      return None

    confirmed = await self._confirm_with_user(detected)
    if not confirmed:
      return None

    refined = await self._refine_with_user(detected)
    return self._format_for_storage(refined)

  def _detect_potential_topic(self, messages: List[str]) -> Dict:
    """Extract potential topic from messages"""
    combined = " ".join(messages)
    return {
        'name': "Draft: " + combined[:50],
        'description':
        combined[:495] + "..." if len(combined) > 500 else combined
    }

  async def _confirm_with_user(self, topic: Dict) -> bool:
    """Get user confirmation for topic creation"""
    # Implementation would go here
    return True

  async def _refine_with_user(self, topic: Dict) -> Dict:
    """Allow user to refine the topic"""
    # Implementation would go here
    return topic

  def _format_for_storage(self, topic: Dict) -> Dict:
    """Format topic for database storage"""
    return {
        'user_id': self.user_id,
        'name': topic['name'],
        'description': topic['description'],
        'created_at': None  # Would be set to current timestamp
    }
