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
from api.agents.models.conversation_models import TopicState, LogState
import re
import string
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer

logger = logging.getLogger(__name__)


class PineconeManager:

  def __init__(self, user_id: int):
    self._validate_settings()
    self.user_id = user_id

    self.embedding = PineconeEmbeddings(model="multilingual-e5-large",
                                        api_key=settings.PINECONE_API_KEY)

    # Initialize stores with separate namespaces
    self.topic_store = Pinecone.from_existing_index(
        embedding=self.embedding,
        index_name=settings.PINECONE_INDEX_NAME,
        namespace="topics")

    self.log_store = Pinecone.from_existing_index(
        embedding=self.embedding,
        index_name=settings.PINECONE_INDEX_NAME,
        namespace="logs")

    self.executor = ThreadPoolExecutor(max_workers=3)

  def _validate_settings(self):
    required = ['PINECONE_INDEX_NAME']
    missing = [key for key in required if not hasattr(settings, key)]
    if missing:
      raise ValueError(f"Missing required settings: {', '.join(missing)}")

  def calculate_time_decay(self, date_updated: datetime) -> float:
    """Calculate decay factor based on time elapsed"""
    now = datetime.now()
    days_elapsed = (now - date_updated).days

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

  async def retrieve_logs(self,
                          embedding: List[float],
                          min_score: float = 0.5,
                          top_k: int = 5) -> List[LogState]:

    try:
      now = datetime.now()
      three_months_ago = now - timedelta(days=90)

      index = self.log_store._index

      # Query with metadata filters
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: index.query(vector=embedding,
                              filter={
                                  "user_id": self.user_id,
                                  "date": {
                                      "$gt": three_months_ago.isoformat(),
                                      "$lt": now.isoformat()
                                  }
                              },
                              top_k=top_k,
                              namespace="logs"))

      logs = []
      for doc, score in results:
        try:
          # Safely access metadata
          if not hasattr(doc, 'metadata'):
            logger.warning(f"Document missing metadata: {doc}")
            continue

          metadata = doc.metadata

          # Extract required fields with explicit type conversion
          topic_name = metadata.get('topic_name')
          if topic_name is None:
            continue

          try:
            topic_name = str(topic_name)
          except (ValueError, TypeError):
            logger.warning(f"Invalid topic_name format: {topic_name}")
            continue

          # Extract other required fields
          topic_name = str(metadata.get('topic_name', ''))
          topic_id = int(metadata.get('topic_id', 0))
          text = str(metadata.get('text', ''))
          date = metadata.get('date')

          if not all([topic_name, text, date]):
            logger.warning(f"Missing required fields in metadata: {metadata}")
            continue

          # Parse date
          try:
            date = datetime.fromisoformat(date)
          except (ValueError, TypeError):
            logger.warning(f"Invalid date format: {date}")
            continue

          # Calculate score with time decay
          adjusted_score = self.adjust_score_with_decay(score, date)
          if adjusted_score < min_score:
            continue

          # Get embedding from metadata
          embedding_values = metadata.get('values')
          if embedding_values is None:
            logger.warning(f"Missing embedding values for log")

          # Create TopicState
          log = LogState(topic_id=topic_id,
                         topic_name=topic_name,
                         text=text,
                         date=date)
          logs.append(log)

        except Exception as e:
          logger.warning(f"Error processing log: {str(e)}")
          continue

      return logs

    except Exception as e:
      logger.error(f"Error retrieving topics: {str(e)}")
      return []

  async def retrieve_topics(self,
                            embedding: List[float],
                            min_score: float = 0.5,
                            top_k: int = 5) -> List[TopicState]:
    """
    Retrieve relevant topics based on embedding similarity and time decay.

    Args:
    embedding: Vector embedding to compare against
    user_id: User ID to filter topics
    min_score: Minimum similarity score threshold
    top_k: Maximum number of topics to return

    Returns:
    List[TopicState]: List of matching topics
    """
    try:
      now = datetime.now()
      three_months_ago = now - timedelta(days=90)

      index = self.topic_store._index

      # Query with metadata filters
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: index.query(vector=embedding,
                              filter={
                                  "user_id": self.user_id,
                                  "last_updated": {
                                      "$gt": three_months_ago.isoformat(),
                                      "$lt": now.isoformat()
                                  }
                              },
                              top_k=top_k,
                              namespace="topics"))

      topics = []
      for doc, score in results:
        try:
          # Safely access metadata
          if not hasattr(doc, 'metadata'):
            logger.warning(f"Document missing metadata: {doc}")
            continue

          metadata = doc.metadata

          # Extract required fields with explicit type conversion
          topic_id = metadata.get('topic_id')
          if topic_id is None:
            continue

          try:
            topic_id = int(topic_id)
          except (ValueError, TypeError):
            logger.warning(f"Invalid topic_id format: {topic_id}")
            continue

          # Extract other required fields
          topic_name = str(metadata.get('topic_name', ''))
          text = str(metadata.get('text', ''))
          date_updated = metadata.get('date_updated')

          if not all([topic_name, text, date_updated]):
            logger.warning(f"Missing required fields in metadata: {metadata}")
            continue

          # Parse date
          try:
            last_updated = datetime.fromisoformat(date_updated)
          except (ValueError, TypeError):
            logger.warning(f"Invalid date format: {date_updated}")
            continue

          # Calculate score with time decay
          adjusted_score = self.adjust_score_with_decay(score, last_updated)
          if adjusted_score < min_score:
            continue

          # Get embedding from metadata
          embedding_values = metadata.get('values')
          if embedding_values is None:
            logger.warning(f"Missing embedding values for topic {topic_id}")

          # Create TopicState
          topic = TopicState(topic_id=topic_id,
                             topic_name=topic_name,
                             embedding=embedding_values,
                             text=text,
                             date_updated=last_updated,
                             confidence=adjusted_score)
          topics.append(topic)

        except Exception as e:
          logger.warning(f"Error processing topic: {str(e)}")
          continue

      return topics

    except Exception as e:
      logger.error(f"Error retrieving topics: {str(e)}")
      return []

  async def get_topic_vector_by_id(self,
                                   topic_id: int) -> Optional[List[float]]:
    """
    Fetch and return only the embedding of a topic by topic_id using LangChain's Pinecone wrapper.

    Args:
        topic_id: The ID of the topic to fetch

    Returns:
        Optional[List[float]]: The embedding vector if found, None otherwise
    """
    try:
      # Use similarity_search with metadata filter
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.topic_store.similarity_search_with_score(
              query="",  # Empty query since we're just filtering
              k=1,
              filter={"topic_id": topic_id}))

      # Check if we got any results
      if results and len(results) > 0:
        doc, score = results[0]
        # The embedding should be in the metadata
        if hasattr(doc, 'metadata') and 'values' in doc.metadata:
          return doc.metadata['values']

      return None

    except Exception as e:
      logger.error(f"Error retrieving topic embedding: {str(e)}")
      return None

  async def get_log_vector_by_id(self, log_id: int) -> Optional[List[float]]:
    """
    Fetch and return only the embedding of a log by log_id using LangChain's Pinecone wrapper.
  
    Args:
    topic_id: The ID of the topic to fetch
  
    Returns:
    Optional[List[float]]: The embedding vector if found, None otherwise
    """
    try:
      # Use similarity_search with metadata filter
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.log_store.similarity_search_with_score(
              query="",  # Empty query since we're just filtering
              k=1,
              filter={"log_id": log_id}))

      # Check if we got any results
      if results and len(results) > 0:
        doc, score = results[0]
        # The embedding should be in the metadata
        if hasattr(doc, 'metadata') and 'values' in doc.metadata:
          return doc.metadata['values']

      return None

    except Exception as e:
      logger.error(f"Error retrieving topic embedding: {str(e)}")
      return None

  async def upsert_topic(self, topic: TopicState) -> List[float]:
    try:
      prepared_text = self.prepare_text_for_embedding(topic.topic_name + " " +
                                                      topic.text)

      # Most vector stores return a dict with 'ids' and 'embeddings'
      result = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.topic_store.add_texts(
              texts=[prepared_text],
              metadatas=[{
                  "topic_id": topic.topic_id,
                  "user_id": self.user_id,
                  "topic_name": topic.topic_name,
                  "text": topic.text,
                  "date_updated": datetime.now().strftime('%Y-%m-%d')
              }],
              return_embeddings=True  # Add this parameter
          ))

      # Extract the embedding from the result
      embeddings = result.get('embeddings', [])
      return embeddings[0] if embeddings else []
    except Exception as e:
      logger.error(f"Error upserting topic: {str(e)}")
      return []

  async def upsert_log(self, log: LogState) -> bool:
    try:

      prepared_text = self.prepare_text_for_embedding(log.topic_name + " " +
                                                      log.text)
      await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.log_store.add_texts(
              # process before embedding
              texts=[prepared_text],
              metadatas=[{
                  "user_id": self.user_id,
                  "topic_id": log.topic_id,
                  "topic_name": log.topic_name,
                  "text": log.text,
                  "chat_session_id": log.chat_session_id,
                  "date": datetime.now().isoformat()
              }]))
      return True
    except Exception as e:
      logger.error(f"Error upserting log: {str(e)}")
      return False

  async def update_topic_vector(self, topic: TopicState) -> bool:
    """
    Update the vector embedding of an existing topic with new text and name.
    Args:
        topic (TopicState): The topic object containing updated information
    Returns:
        bool: True if update successful, False otherwise
    """
    prepared_text = self.prepare_text_for_embedding(topic.topic_name + " " +
                                                    topic.text)

    try:
      # Generate new embedding for the text
      new_embedding = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.embedding.embed_query(prepared_text))

      # Get the existing metadata
      existing_docs = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_store.get_by_metadata(
              {'topic_id': topic.topic_id}))

      if not existing_docs:
        logger.error(f"Topic with ID {topic.topic_id} not found")
        return False

      existing_metadata = existing_docs[0].metadata

      # Update the metadata with new values and current timestamp
      updated_metadata = {
          **existing_metadata, "topic_name": topic.topic_name,
          "text": topic.text,
          "date_updated": datetime.now().strftime('%Y-%m-%d')
      }

      # Delete the old vector
      await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.topic_store.delete(filter={"topic_id": topic.topic_id}))

      # Insert the new vector with updated metadata
      await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.topic_store.add_texts(texts=[prepared_text],
                                             embeddings=[new_embedding],
                                             metadatas=[updated_metadata]))

      return True

    except Exception as e:
      logger.error(f"Error updating topic vector: {str(e)}")
      return False

  def prepare_text_for_embedding(self,
                                 text,
                                 remove_stopwords=True,
                                 use_stemming=False,
                                 use_lemmatization=True):
    """
      Prepares text for embedding by cleaning and normalizing it.

      Args:
          text (str): The input text to be prepared
          remove_stopwords (bool): Whether to remove stopwords
          use_stemming (bool): Whether to apply stemming
          use_lemmatization (bool): Whether to apply lemmatization

      Returns:
          str: The prepared text
      """
    # Check if text is empty or None
    if not text:
      return ""

    # Convert to lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)

    # Remove special characters and numbers
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', ' ', text)

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Tokenize the text
    tokens = text.split()

    # Remove stopwords if specified
    if remove_stopwords:
      try:
        stop_words = set(stopwords.words('english'))
        tokens = [token for token in tokens if token not in stop_words]
      except LookupError:
        # If NLTK stopwords aren't available, continue without removing them
        pass

    # Apply stemming if specified
    if use_stemming:
      try:
        stemmer = PorterStemmer()
        tokens = [stemmer.stem(token) for token in tokens]
      except:
        # Continue without stemming if there's an error
        pass

    # Apply lemmatization if specified
    if use_lemmatization and not use_stemming:  # Don't apply both
      try:
        lemmatizer = WordNetLemmatizer()
        tokens = [lemmatizer.lemmatize(token) for token in tokens]
      except:
        # Continue without lemmatizing if there's an error
        pass

    # Join tokens back into text
    prepared_text = ' '.join(tokens)

    return prepared_text
