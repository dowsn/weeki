from typing import List, Dict, Optional
from datetime import datetime, timedelta
from langchain_community.vectorstores import Pinecone
from django.conf import settings
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from langchain_pinecone import PineconeEmbeddings
from django.conf import settings
from api.agents.models.conversation_models import ConversationState
from api.agents.models.conversation_models import TopicState

logger = logging.getLogger(__name__)


class PineconeManager:

  def __init__(self):
    self._validate_settings()

    self.embedding = PineconeEmbeddings(model="multilingual-e5-large",
                                        api_key=settings.PINECONE_API_KEY)

    # Initialize stores with separate namespaces
    self.topic_store = Pinecone.from_existing_index(
        embedding=self.embedding,
        index_name=settings.PINECONE_INDEX,
        namespace="topics")

    self.log_store = Pinecone.from_existing_index(
        embedding=self.embedding,
        index_name=settings.PINECONE_INDEX,
        namespace="logs")

    self.executor = ThreadPoolExecutor(max_workers=3)

  def _validate_settings(self):
    required = ['PINECONE_INDEX']
    missing = [key for key in required if not hasattr(settings, key)]
    if missing:
      raise ValueError(f"Missing required settings: {', '.join(missing)}")

  def calculate_time_decay(self, last_updated: datetime) -> float:
    """Calculate decay factor based on time elapsed"""
    now = datetime.now()
    days_elapsed = (now - last_updated).days

    # Exponential decay with half-life of 30 days
    half_life = 30
    decay_factor = 0.5**(days_elapsed / half_life)
    return max(0.1, decay_factor)  # Minimum decay of 0.1

  def adjust_score_with_decay(self, base_score: float,
                              last_updated: datetime) -> float:
    """Combine similarity score with time decay"""
    time_decay = self.calculate_time_decay(last_updated)
    # Weight: 70% similarity, 30% time freshness
    return (0.7 * base_score) + (0.3 * time_decay)

  async def retrieve_topics(self,
                            embedding: List[float],
                            user_id: int,
                            min_score: float = 0.5,
                            top_k: int = 5):

    try:
      now = datetime.now()
      # only last three months?
      three_months_ago = now - timedelta(days=90)

      results = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_store.similarity_search_with_score(
              embedding,
              k=top_k,
              filter={
                  "user_id": user_id,
                  "last_updated": {
                      "$gt": three_months_ago.isoformat(),
                      "$lt": now.isoformat()
                  }
              }))

      topics = []
      for doc, score in results:
        last_updated = datetime.fromisoformat(doc.metadata.get('last_updated'))
        adjusted_score = self.adjust_score_with_decay(score, last_updated)

        if adjusted_score >= min_score:
          # fix
          topic = TopicState(id=doc.metadata.get('topic_id'),
                             name=doc.metadata.get('name'),
                             embedding=doc.embedding,
                             description=doc.page_content,
                             confidence=adjusted_score)
          topics.append(topic)

      return topics

    except Exception as e:
      logger.error(f"Error retrieving topics: {str(e)}")
      return []

  async def retrieve_logs(self,
                          embedding: List[float],
                          user_id: int,
                          top_k: int = 5) -> List[str]:
    try:
      now = datetime.now()
      one_month_ago = now - timedelta(days=30)

      # topic_ids = [t.id for t in topics if t.id is not None]
      # if not topic_ids:
      #   return []

      results = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.log_store.similarity_search_with_score(
              embedding,
              k=top_k,
              filter={
                  "user_id": user_id,
                  "topic_id": {
                      "$in": topic_ids
                  },
                  "date": {
                      "$gt": one_month_ago.isoformat(),
                      "$lt": now.isoformat()
                  }
              }))

      logs = [(doc.page_content, score) for doc, score in results]
      logs.sort(key=lambda x: x[1], reverse=True)
      return [log[0] for log in logs]

    except Exception as e:
      logger.error(f"Error retrieving logs: {str(e)}")
      return []

  async def get_topic_vector_by_id(self, topic_id: str) -> Optional[List[float]]:
      """Fetch and return only the embedding of a topic by topic_id."""
      try:
          result = await asyncio.get_event_loop().run_in_executor(
              self.executor, lambda: self.topic_store.get_by_metadata({'topic_id': topic_id})
          )
          if result:
              return result[0].embedding
          return None
      except Exception as e:
          logger.error(f"Error retrieving topic embedding: {str(e)}")
          return None
  
  

  async def upsert_topic(self, topic: TopicState, user_id: int) -> bool:
    try:
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_store.add_texts(
              texts=[topic.description],
              metadatas=[{
                  "topic_id": topic.id,
                  "user_id": user_id,
                  "name": topic.name,
                  "last_updated": datetime.now().isoformat()
              }]))
      return True
    except Exception as e:
      logger.error(f"Error upserting topic: {str(e)}")
      return False

  async def upsert_log(self, log_text: str, user_id: int, topic_id: int,
                       chat_session_id: int) -> bool:
    try:
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.log_store.add_texts(
              texts=[log_text],
              metadatas=[{
                  "user_id": user_id,
                  "topic_id": topic_id,
                  "chat_session_id": chat_session_id,
                  "date": datetime.now().isoformat()
              }]))
      return True
    except Exception as e:
      logger.error(f"Error upserting log: {str(e)}")
      return False
