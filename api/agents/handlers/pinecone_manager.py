from typing import List, Dict, Optional
from datetime import datetime, timedelta
from langchain_community.vectorstores import Pinecone
from django.conf import settings
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from langchain_pinecone import PineconeEmbeddings
from api.agents.models.conversation_models import ConversationState
from api.agents.models.conversation_models import TopicState, LogState
import re
import string
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer
from app.models import Topic, Log

# LlamaIndex imports
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import Document, NodeWithScore, TextNode
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import Settings
# Create a VectorStoreQuery object
from llama_index.core.vector_stores.types import VectorStoreQuery
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

logger = logging.getLogger(__name__)


class PineconeManager:

  def __init__(self, user_id: int):
    self._validate_settings()
    self.user_id = user_id

    self.embedding_model = OpenAIEmbedding(model="text-embedding-3-small",
                                           api_key=settings.OPENAI_API_KEY)
    Settings.embed_model = self.embedding_model

    # Initialize Pinecone vector stores with separate namespaces
    self.topic_store = PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        environment=settings.PINECONE_ENVIRONMENT,
        namespace="topics",
        api_key=settings.PINECONE_API_KEY)

    self.log_store = PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        environment=settings.PINECONE_ENVIRONMENT,
        namespace="logs",
        api_key=settings.PINECONE_API_KEY)

    # Create indexes
    self.topic_storage_context = StorageContext.from_defaults(
        vector_store=self.topic_store)
    self.log_storage_context = StorageContext.from_defaults(
        vector_store=self.log_store)

    self.topic_index = VectorStoreIndex.from_vector_store(
        vector_store=self.topic_store,
        storage_context=self.topic_storage_context)

    self.log_index = VectorStoreIndex.from_vector_store(
        vector_store=self.log_store, storage_context=self.log_storage_context)

    # Create executor for async operations
    self.executor = ThreadPoolExecutor(max_workers=3)

  def _validate_settings(self):
    required = ['PINECONE_INDEX_NAME']
    missing = [key for key in required if not hasattr(settings, key)]
    if missing:
      raise ValueError(f"Missing required settings: {', '.join(missing)}")

  async def get_text_embedding(self, text: str) -> List[float]:
    """Get embedding for text using the configured embedding model"""
    return await asyncio.get_event_loop().run_in_executor(
        self.executor, lambda: self.embedding_model.get_text_embedding(text))

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

  class TimeDecayRetriever(BaseRetriever):
    """Custom retriever that applies time-decay to relevance scores"""

    def __init__(self, vector_store, user_id, calculate_time_decay_fn,
                 adjust_score_fn, parent_manager):
      self.vector_store = vector_store
      self.user_id = user_id
      self.embedding_model = Settings.embed_model
      self.calculate_time_decay = calculate_time_decay_fn
      self.adjust_score = adjust_score_fn
      self.parent_manager = parent_manager

    def _retrieve(self,
                  query_embedding,
                  min_score=0.5,
                  top_k=5,
                  time_filter=True):
      # Import the necessary classes

      # Build filters
      filter_list = [
          MetadataFilter(key="user_id",
                         operator=FilterOperator.EQ,
                         value=str(self.user_id))
      ]

      # Add time filter if requested
      if time_filter:
        now = datetime.now()
        three_months_ago = now - timedelta(days=90)

        # Convert to Unix timestamps (seconds since epoch)
        now_timestamp = now.timestamp()
        three_months_ago_timestamp = three_months_ago.timestamp()

        filter_list.append(
            MetadataFilter(key="date_updated",  # Same field name as in your data
                           operator=FilterOperator.GTE,
                           value=three_months_ago_timestamp))
        filter_list.append(
            MetadataFilter(key="date_updated",
                           operator=FilterOperator.LTE,
                           value=now_timestamp))

      # Create metadata filters
      filters = MetadataFilters(filters=filter_list)

      # Create query
      vector_store_query = VectorStoreQuery(query_embedding=query_embedding,
                                            similarity_top_k=top_k,
                                            filters=filters)

      # Execute query
      query_result = self.vector_store.query(vector_store_query)

      # Process results
      adjusted_results = []
      for node_with_score in query_result.nodes:
        try:
          node = node_with_score.node
          score = node_with_score.score
          metadata = node.metadata
          date_str = metadata.get("date")

          if date_str:
            date = datetime.fromisoformat(date_str)
            adjusted_score = self.adjust_score(score, date)

            if adjusted_score >= min_score:
              # Create a new NodeWithScore with adjusted score
              adjusted_node_with_score = NodeWithScore(node=node,
                                                       score=adjusted_score)
              adjusted_results.append(adjusted_node_with_score)
        except Exception as e:
          logger.warning(f"Error processing result: {str(e)}")
          continue

      return adjusted_results

    async def retrieve(self, query, **kwargs):
      # Get embedding for query
      if isinstance(query, str):
        query_embedding = await self.parent_manager.get_text_embedding(query)
      else:
        # Assume it's already an embedding
        query_embedding = query

      min_score = kwargs.get("min_score", 0.5)
      top_k = kwargs.get("top_k", 5)
      time_filter = kwargs.get("time_filter", True)

      return self._retrieve(query_embedding=query_embedding,
                            min_score=min_score,
                            top_k=top_k,
                            time_filter=time_filter)

  async def retrieve_topics(self,
                            embedding: List[float],
                            min_score: float = 0.5,
                            top_k: int = 5) -> List[TopicState]:
    """
    Retrieve topics similar to the embedding with time-decay applied to scores.

    Args:
        embedding: Query embedding vector
        min_score: Minimum similarity score (after decay)
        top_k: Maximum number of results

    Returns:
        List[TopicState]: List of retrieved topics
    """
    try:
      # Create an instance of our custom retriever
      retriever = self.TimeDecayRetriever(
          vector_store=self.topic_store,
          user_id=self.user_id,
          calculate_time_decay_fn=self.calculate_time_decay,
          adjust_score_fn=self.adjust_score_with_decay,
          parent_manager=self)

      # Use executor to run retrieval in a thread
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: retriever._retrieve(
              query_embedding=embedding, min_score=min_score, top_k=top_k))

      # Convert results to TopicState objects
      topics = []
      for node_with_score in results:
        try:
          node = node_with_score.node
          metadata = node.metadata

          # Extract required fields with explicit type conversion
          topic_id = metadata.get('topic_id')
          if topic_id is None:
            continue

          try:
            topic_id = int(topic_id)
            topic = Topic.objects.get(id=topic_id)
          except (ValueError, TypeError):
            logger.warning(f"Invalid topic_id format: {topic_id}")
            continue

          date_updated_str = metadata.get('date_updated')

          if not topic:
            logger.warning("Missing topic")
            continue

          # Parse date
          try:
            date_updated = datetime.fromisoformat(date_updated_str)
          except (ValueError, TypeError):
            logger.warning(f"Invalid date format: {date_updated_str}")
            continue

          # Calculate confidence from score (already adjusted with time decay)
          confidence = node_with_score.score

          # Get embedding
          node_embedding = node.embedding if hasattr(node,
                                                     'embedding') else None
          embedding = node_embedding if node_embedding is not None else []

          # Create TopicState
          topic = TopicState(topic_id=topic_id,
                             topic_name=topic.name,
                             text=topic.description,
                             confidence=confidence,
                             embedding=embedding,
                             date_updated=date_updated)

          topics.append(topic)

        except Exception as e:
          logger.warning(f"Error processing topic: {str(e)}")
          continue

      return topics

    except Exception as e:
      logger.error(f"Error retrieving topics: {str(e)}")
      return []

  async def retrieve_logs(self,
                          embedding: List[float],
                          min_score: float = 0.5,
                          top_k: int = 5) -> List[LogState]:
    """
    Retrieve logs similar to the query with time-decay applied to scores.
  
    Args:
    query: Query string or embedding
    min_score: Minimum similarity score (after decay)
    top_k: Maximum number of results
  
    Returns:
    List[LogState]: List of retrieved logs
    """
    try:
      # Create an instance of our custom retriever
      retriever = self.TimeDecayRetriever(
          vector_store=self.log_store,
          user_id=self.user_id,
          calculate_time_decay_fn=self.calculate_time_decay,
          adjust_score_fn=self.adjust_score_with_decay,
          parent_manager=self)

      # Get embedding for query if it's a string

      # Use executor to run retrieval in a thread
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: retriever.retrieve(
              embedding, min_score=min_score, top_k=top_k))

      # Convert results to LogState objects
      logs = []
      for node_with_score in results:
        try:
          node = node_with_score.node
          metadata = node.metadata

          topic_id = metadata.get('topic_id')

          @database_sync_to_async
          def get_topic_and_log():
              topic = Topic.objects.get(id=topic_id)
              if not topic:
                  return None, None

              log = Log.objects.get(id=metadata.get('log_id'))
              return topic, log

          topic, log = await get_topic_and_log()

          if not topic or not log:
              continue

          date_str = metadata.get('date')

          try:
            date = datetime.fromisoformat(date_str)
          except (ValueError, TypeError):
            logger.warning(f"Invalid date format: {date_str}")
            continue

          # Create LogState
          log = LogState(topic_id=topic_id,
                         topic_name=topic.name,
                         text=log.text,
                         date=date)

          logs.append(log)

        except Exception as e:
          logger.warning(f"Error processing log: {str(e)}")
          continue

      return logs

    except Exception as e:
      logger.error(f"Error retrieving logs: {str(e)}")
      return []

  async def get_topic_vector_by_id(self,
                                   topic_id: int) -> Optional[List[float]]:
    """
    Fetch and return only the embedding of a topic by topic_id.

    Args:
        topic_id: The ID of the topic to fetch

    Returns:
        Optional[List[float]]: The embedding vector if found, None otherwise
    """
    try:
      # Import the necessary classes

      # Create filter for topic_id
      filters = MetadataFilters(filters=[
          MetadataFilter(
              key="topic_id", operator=FilterOperator.EQ, value=str(topic_id))
      ])

      # Create a retriever from the index with the filters
      retriever = self.topic_index.as_retriever(filters=filters)

      # Use an empty query string instead of a dummy embedding
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: retriever.retrieve("")  # Empty query string
      )

      # Check if we got results
      if results and len(results) > 0:
        node = results[0].node
        # The embedding should be accessible through node properties
        if hasattr(node, 'embedding') and node.embedding is not None:
          return node.embedding

      return None

    except Exception as e:
      logger.error(f"Error retrieving topic embedding: {str(e)}")
      return None

  async def get_log_vector_by_id(self, log_id: int) -> Optional[List[float]]:
    """
    Fetch and return only the embedding of a log by log_id.

    Args:
        log_id: The ID of the log to fetch

    Returns:
        Optional[List[float]]: The embedding vector if found, None otherwise
    """
    try:
      # Create a dummy query with filter for log_id

      # Import the necessary classes
      from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

      # Create filter for log_id
      filters = MetadataFilters(filters=[
          MetadataFilter(
              key="log_id", operator=FilterOperator.EQ, value=str(log_id))
      ])

      # Create a retriever from the index with the filters
      retriever = self.log_index.as_retriever(filters=filters)

      # Use the retriever to get the node
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: retriever.retrieve(""))

      # Check if we got results
      if results and len(results) > 0:
        node = results[0].node
        # The embedding should be accessible through node properties
        if hasattr(node, 'embedding') and node.embedding is not None:
          return node.embedding

      return None

    except Exception as e:
      logger.error(f"Error retrieving log embedding: {str(e)}")
      return None

  #

  async def upsert_topic(self, topic: TopicState) -> List[float]:
    """
    Insert or update a topic in the vector store.

    Args:
        topic: The topic to upsert

    Returns:
        List[float]: The embedding of the inserted topic
    """
    try:
      # Prepare text for embedding
      prepared_text = self.prepare_text_for_embedding(topic.topic_name + " " +
                                                      topic.text)

      # Create document
      doc = Document(text=prepared_text,
                     metadata={
                         "topic_id": topic.topic_id,
                         "user_id": self.user_id,
                         "date_updated": datetime.now().isoformat()
                     })

      # Get embedding
      embedding = await self.get_text_embedding(prepared_text)

      now = datetime.now()
      metadata = {
          "topic_id": topic.topic_id,
          "user_id": self.user_id,
          "date_updated": now.timestamp()  # Store as numeric timestamp instead of ISO string
      }

      # Create node with the numeric timestamp
      node = TextNode(text=prepared_text,
                      metadata=metadata,
                      embedding=embedding)

      # Insert the node
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_index.insert_nodes([node]))

      return embedding

    except Exception as e:
      logger.error(f"Error upserting topic: {str(e)}")
      return []

  async def upsert_log(self, log: LogState) -> bool:
    """
    Insert a log entry into the vector store.

    Args:
        log: The log to insert

    Returns:
        bool: True if successful, False otherwise
    """
    try:
      # Prepare text for embedding
      prepared_text = self.prepare_text_for_embedding(log.topic_name + " " +
                                                      log.text)
      now = datetime.now()

      metadata={
           "user_id": self.user_id,
           "topic_id": log.topic_id,
           "chat_session_id": log.chat_session_id,
           "date": now.timestamp()
       }
      # Create document
      doc = Document(text=prepared_text,
                     metadata=metadata)

      # Get embedding
      embedding = await self.get_text_embedding(prepared_text)

      # Create node
      node = TextNode(text=prepared_text,
                      metadata=metadata,
                      embedding=embedding)

      # Insert the node
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.log_index.insert_nodes([node]))

      return True

    except Exception as e:
      logger.error(f"Error upserting log: {str(e)}")
      return False

  async def update_topic_vector(self, topic: TopicState) -> bool:
    """
    Update the vector embedding of an existing topic with new text and name.

    Args:
        topic: The topic object containing updated information

    Returns:
        bool: True if update successful, False otherwise
    """
    try:
      # Prepare text for embedding
      prepared_text = self.prepare_text_for_embedding(topic.topic_name + " " +
                                                      topic.text)

      # Generate new embedding
      embedding = await self.get_text_embedding(prepared_text)

      # Delete existing topic
      await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: self.topic_store.delete(filters={"topic_id": topic.topic_id})
      )

      # Create new node with updated data
      node = TextNode(text=prepared_text,
                      metadata={
                          "topic_id": topic.topic_id,
                          "user_id": self.user_id,
                          "date_updated": datetime.now().isoformat()
                      },
                      embedding=embedding)

      # Insert the updated node
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_index.insert_nodes([node]))

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
