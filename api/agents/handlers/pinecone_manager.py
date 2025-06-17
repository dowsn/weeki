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

  class TimeDecayRetriever(BaseRetriever):
    """Custom retriever that applies time-boost to relevance scores"""

    def __init__(self, vector_store, user_id, calculate_time_boost_fn,
                 adjust_score_fn, parent_manager):
      self.vector_store = vector_store
      self.user_id = user_id
      self.embedding_model = Settings.embed_model
      self.calculate_time_boost = calculate_time_boost_fn
      self.adjust_score = adjust_score_fn
      self.parent_manager = parent_manager

    def _retrieve(
        self,
        query_embedding,
        base_similarity_threshold=0.4,  # Stage 1: semantic relevance
        final_score_threshold=0.5,  # Stage 3: final quality threshold
        top_k=10,  # Get more candidates initially
        max_results=3):  # Final result limit

      # Build filters - only user_id for now
      filter_list = [
          MetadataFilter(key="user_id",
                         operator=FilterOperator.EQ,
                         value=str(self.user_id))
      ]

      # Create metadata filters
      filters = MetadataFilters(filters=filter_list)

      # Create query - get more candidates initially
      vector_store_query = VectorStoreQuery(query_embedding=query_embedding,
                                            similarity_top_k=top_k,
                                            filters=filters)

      # Execute query
      query_result = self.vector_store.query(vector_store_query)
      print(f"🔧 RETRIEVER: Found {len(query_result.nodes)} raw results from vector store")
      print(f"🔧 RETRIEVER: Vector store namespace: {getattr(self.vector_store, 'namespace', 'unknown')}")
      print(f"🔧 RETRIEVER: Query filters: user_id={self.user_id}")

      # Debug: Check what attributes are available on query_result
      print(f"🔧 DEBUG: query_result type: {type(query_result)}")
      print(f"🔧 DEBUG: query_result attributes: {dir(query_result)}")
      if hasattr(query_result, 'similarities'):
        print(f"🔧 DEBUG: query_result.similarities: {query_result.similarities}")
      if hasattr(query_result, 'scores'):
        print(f"🔧 DEBUG: query_result.scores: {query_result.scores}")

      # Convert TextNode results to NodeWithScore using scores from query_result
      node_with_scores = []
      if hasattr(query_result, 'nodes') and hasattr(query_result, 'similarities'):
        # If we have both nodes and similarities, create NodeWithScore objects
        print("🔧 DEBUG: Using nodes and similarities")
        for i, node in enumerate(query_result.nodes):
          if i < len(query_result.similarities):
            score = query_result.similarities[i]
            node_with_score = NodeWithScore(node=node, score=score)
            node_with_scores.append(node_with_score)
            print(f"🔧 DEBUG: Created NodeWithScore with score {score}")
      elif hasattr(query_result, 'nodes'):
        # Fallback: try to get scores from the nodes themselves or use a default
        print("🔧 DEBUG: Using fallback method")
        for node in query_result.nodes:
          if hasattr(node, 'score'):
            node_with_score = NodeWithScore(node=node, score=node.score)
          else:
            # Create with a default score if none available
            node_with_score = NodeWithScore(node=node, score=0.0)
          node_with_scores.append(node_with_score)

      print(f"Created {len(node_with_scores)} NodeWithScore objects")

      # Stage 1: Filter by base similarity (semantic relevance)
      semantically_relevant = []
      for node_with_score in node_with_scores:
        score = node_with_score.score
        if score >= base_similarity_threshold:
          semantically_relevant.append(node_with_score)
          print(f"Passed semantic filter: score={score:.3f}")
        else:
          print(f"Filtered out semantically: score={score:.3f}")

      print(f"After semantic filtering: {len(semantically_relevant)} results")

      # Stage 2: Apply time boost to semantically relevant topics
      time_boosted_results = []
      for node_with_score in semantically_relevant:
        try:
          node = node_with_score.node
          base_score = node_with_score.score
          metadata = node.metadata

          # Handle timestamp format (both numeric and ISO string)
          date_updated_value = metadata.get("date_updated")

          if date_updated_value:
            try:
              if isinstance(date_updated_value, (int, float)):
                date = datetime.fromtimestamp(date_updated_value)
              else:
                date = datetime.fromisoformat(str(date_updated_value))
            except (ValueError, TypeError):
              date = datetime.now()
              logger.warning(f"Could not parse date: {date_updated_value}")
          else:
            date = datetime.now()

          # Apply time boost
          boosted_score = self.adjust_score(base_score, date)

          # Create new NodeWithScore with boosted score
          boosted_node_with_score = NodeWithScore(node=node,
                                                  score=boosted_score)
          time_boosted_results.append(boosted_node_with_score)

        except Exception as e:
          logger.warning(f"Error processing result: {str(e)}")
          continue

      # Sort by boosted score (highest first)
      time_boosted_results.sort(key=lambda x: x.score, reverse=True)

      # Stage 3: Apply final threshold and limit results
      final_results = []
      for node_with_score in time_boosted_results:
        if node_with_score.score >= final_score_threshold and len(
            final_results) < max_results:
          final_results.append(node_with_score)
          print(f"Final result: score={node_with_score.score:.3f}")
        elif node_with_score.score < final_score_threshold:
          print(
              f"Filtered out by final threshold: score={node_with_score.score:.3f}"
          )

      print(f"Final results: {len(final_results)} topics")
      return final_results

    async def retrieve(self, query, **kwargs):
      """Handle both string queries and embeddings"""
      # Get embedding for query
      if isinstance(query, str):
        query_embedding = await self.parent_manager.get_text_embedding(query)
      else:
        query_embedding = query

      # Map old parameters to new ones for backward compatibility
      base_threshold = kwargs.get("base_threshold",
                                  kwargs.get("min_score", 0.4))
      final_threshold = kwargs.get("final_threshold", 0.5)
      max_results = kwargs.get("max_results", kwargs.get("top_k", 3))

      return self._retrieve(query_embedding=query_embedding,
                            base_similarity_threshold=base_threshold,
                            final_score_threshold=final_threshold,
                            max_results=max_results)

  async def retrieve_topics(
      self,
      embedding: List[float],
      base_threshold: float = 0.4,  # Semantic relevance threshold
      final_threshold: float = 0.5,  # Final quality threshold
      max_results: int = 3) -> List[TopicState]:

    try:
      # Create retriever with time boost functions
      retriever = self.TimeDecayRetriever(
          vector_store=self.topic_store,
          user_id=self.user_id,
          calculate_time_boost_fn=self.calculate_time_boost,
          adjust_score_fn=self.adjust_score_with_time_boost,
          parent_manager=self)

      # Use executor to run retrieval in a thread
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: retriever._retrieve(query_embedding=embedding,
                                      base_similarity_threshold=base_threshold,
                                      final_score_threshold=final_threshold,
                                      max_results=max_results))

      # Convert results to TopicState objects
      topics = []
      for node_with_score in results:
        try:
          node = node_with_score.node
          metadata = node.metadata

          topic_id = metadata.get('topic_id')
          if topic_id is None:
            continue

          try:
            topic_id = int(topic_id)
            
            # Use sync_to_async for Django ORM call
            from asgiref.sync import sync_to_async
            @sync_to_async
            def get_topic():
              return Topic.objects.get(id=topic_id)
            
            topic = await get_topic()
          except (ValueError, TypeError, Topic.DoesNotExist) as e:
            logger.warning(f"Invalid topic_id or topic not found: {topic_id}")
            continue

          # Parse date for TopicState
          date_updated_value = metadata.get("date_updated")
          if date_updated_value:
            try:
              if isinstance(date_updated_value, (int, float)):
                date_updated = datetime.fromtimestamp(date_updated_value)
              else:
                date_updated = datetime.fromisoformat(str(date_updated_value))
            except (ValueError, TypeError):
              date_updated = datetime.now()
          else:
            date_updated = datetime.now()

          # Create TopicState
          topic_state = TopicState(
              topic_id=topic_id,
              topic_name=topic.name,
              text=topic.description,
              confidence=node_with_score.score,  # This is the boosted score
              embedding=[],
              date_updated=date_updated)

          topics.append(topic_state)
          print(
              f"Added topic: {topic.name} (score: {node_with_score.score:.3f})"
          )

        except Exception as e:
          logger.warning(f"Error processing topic: {str(e)}")
          continue

      print(f"Returning {len(topics)} topics")
      return topics

    except Exception as e:
      logger.error(f"Error retrieving topics: {str(e)}")
      return []

  async def retrieve_logs(self,
                          embedding: List[float],
                          base_threshold: float = 0.4,
                          final_threshold: float = 0.5,
                          max_results: int = 5) -> List[LogState]:
    """
    Retrieve logs similar to the query with time-boost applied to scores.
    """
    print(f"🔍 PINECONE: Starting retrieve_logs for user_id={self.user_id}")
    print(f"🔍 PINECONE: Embedding length: {len(embedding)}")
    print(f"🔍 PINECONE: Thresholds - base: {base_threshold}, final: {final_threshold}")
    
    try:
      # Create retriever with time BOOST functions (not decay)
      retriever = self.TimeDecayRetriever(
          vector_store=self.log_store,
          user_id=self.user_id,
          calculate_time_boost_fn=self.calculate_time_boost,
          adjust_score_fn=self.adjust_score_with_time_boost,
          parent_manager=self)

      print("🔍 PINECONE: Created TimeDecayRetriever for logs namespace")

      # Use the new 3-stage retrieval system
      results = await asyncio.get_event_loop().run_in_executor(
          self.executor,
          lambda: retriever._retrieve(query_embedding=embedding,
                                      base_similarity_threshold=base_threshold,
                                      final_score_threshold=final_threshold,
                                      max_results=max_results))

      print(f"🔍 PINECONE: Raw retrieval returned {len(results)} results")

      # Convert results to LogState objects
      logs = []
      for i, node_with_score in enumerate(results):
        print(f"🔍 PINECONE: Processing result {i+1}")
        try:
          node = node_with_score.node
          metadata = node.metadata
          print(f"🔍 PINECONE: Node metadata: {metadata}")

          topic_id = metadata.get('topic_id')
          chat_session_id = metadata.get('chat_session_id')
          print(f"🔍 PINECONE: Extracted topic_id={topic_id}, chat_session_id={chat_session_id}")

          from asgiref.sync import sync_to_async
          
          @sync_to_async
          def get_topic_and_logs():
            try:
              topic = Topic.objects.get(id=topic_id)
              # Get logs by chat_session_id, not by log id
              logs = Log.objects.filter(chat_session_id=chat_session_id)
              log_count = logs.count()  # Execute count query while in sync context
              topic_name = topic.name   # Access attribute while in sync context
              print(f"🔍 PINECONE: Found topic '{topic_name}' and {log_count} logs for session {chat_session_id}")
              return topic, logs, topic_name, log_count
            except (Topic.DoesNotExist, AttributeError) as e:
              print(f"🔍 PINECONE: Error getting topic/logs: {e}")
              return None, None, None, 0

          topic, session_logs, topic_name, log_count = await get_topic_and_logs()

          if not topic:
            print(f"🔍 PINECONE: No topic found for topic_id={topic_id}")
            continue
          if not session_logs:
            print(f"🔍 PINECONE: No logs found for chat_session_id={chat_session_id}")
            continue

          # Parse date
          date_updated_value = metadata.get('date_updated')
          if date_updated_value:
            try:
              if isinstance(date_updated_value, (int, float)):
                date = datetime.fromtimestamp(date_updated_value)
              else:
                date = datetime.fromisoformat(str(date_updated_value))
            except (ValueError, TypeError):
              date = datetime.now()
          else:
            date = datetime.now()

          # Create LogState for each log in the session (or just use the text from the node)
          # Since the node text contains the prepared text, we'll use that
          log_state = LogState(
              topic_id=topic_id,
              topic_name=topic_name,
              text=node.text,  # Use the text from the vector store node
              date=date,
              chat_session_id=chat_session_id,
              confidence=node_with_score.score)  # Add confidence

          logs.append(log_state)
          print(f"🔍 PINECONE: Created LogState for topic '{topic_name}' with confidence {node_with_score.score:.3f}")

        except Exception as e:
          print(f"🔍 PINECONE: Error processing log result {i+1}: {str(e)}")
          logger.warning(f"Error processing log: {str(e)}")
          continue

      print(f"🔍 PINECONE: Returning {len(logs)} final logs")
      return logs

    except Exception as e:
      print(f"🔍 PINECONE: Major error in retrieve_logs: {str(e)}")
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
      # Create filter for topic_id and user_id
      # Fix typing issue by explicitly typing the list or constructing directly
      filters = MetadataFilters(filters=[
          MetadataFilter(
              key="topic_id", operator=FilterOperator.EQ, value=str(topic_id)),
          MetadataFilter(key="user_id",
                         operator=FilterOperator.EQ,
                         value=str(self.user_id))
      ])

      # Create a dummy query vector (all zeros) since we only care about the filter
      # The embedding dimension should match your model (1536 for text-embedding-3-small)
      dummy_vector = [0.0] * 1536

      # Create vector store query with the dummy vector and filters
      vector_store_query = VectorStoreQuery(
          query_embedding=dummy_vector,
          similarity_top_k=1,  # We only want one result
          filters=filters)

      # Execute query using the vector store directly
      query_result = await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_store.query(vector_store_query))

      # Check if we got results
      if query_result.nodes and len(query_result.nodes) > 0:
        node = query_result.nodes[0].node
        # The embedding should be accessible through node properties
        if hasattr(node, 'embedding') and node.embedding is not None:
          return node.embedding

      return None

    except Exception as e:
      logger.error(f"Error retrieving topic embedding: {str(e)}")
      return None

  def calculate_time_boost(self,
                           date_updated: datetime,
                           max_boost=0.5) -> float:
    """
    Calculate time boost - newer items get higher boost
    max_boost: maximum boost factor (0.5 = 50% score increase)
    """
    now = datetime.now()
    days_elapsed = (now - date_updated).days

    # Recent items (< 7 days) get full boost
    if days_elapsed < 7:
      return max_boost
    # Items within 30 days get declining boost
    elif days_elapsed < 30:
      return max_boost * (1 - (days_elapsed - 7) / 23)  # Linear decline
    # Items within 90 days get small boost
    elif days_elapsed < 90:
      return max_boost * 0.1  # Small boost
    # Older items get no boost
    else:
      return 0.0

  def adjust_score_with_time_boost(self, base_score: float,
                                   last_updated: datetime) -> float:
    """Apply time boost to base score"""
    time_boost = self.calculate_time_boost(last_updated)
    return base_score * (1 + time_boost)

  async def upsert_topic(self, topic: TopicState) -> List[float]:
    try:
      # Prepare text for embedding
      prepared_text = self.prepare_text_for_embedding(topic.topic_name + " " +
                                                      topic.text)
      print("embedding this text:", prepared_text)

      # Get embedding
      embedding = await self.get_text_embedding(prepared_text)

      # Use consistent metadata format
      metadata = {
          "topic_id": str(topic.topic_id),  # Always string
          "user_id": str(self.user_id),  # Always string  
          "date_updated":
          datetime.now().timestamp()  # Always numeric timestamp
      }

      # Create node
      node = TextNode(text=prepared_text,
                      metadata=metadata,
                      embedding=embedding)

      # Insert the node
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.topic_index.insert_nodes([node]))

      print(f"Successfully upserted topic {topic.topic_id}")
      return embedding

    except Exception as e:
      logger.error(f"Error upserting topic: {str(e)}")
      return []

  async def upsert_log(self, log: LogState) -> bool:
    """
    Insert a log entry into the vector store.
    """
    try:
      # Prepare text for embedding
      prepared_text = self.prepare_text_for_embedding(log.topic_name + " " +
                                                      log.text)

      # Use consistent metadata format (all strings like topics)
      metadata = {
          "user_id": str(self.user_id),  # Consistent string format
          "topic_id": str(log.topic_id),  # Consistent string format
          "chat_session_id":
          str(log.chat_session_id),  # Consistent string format
          "date_updated":
          datetime.now().timestamp()  # Consistent timestamp format
      }

      # Get embedding
      embedding = await self.get_text_embedding(prepared_text)

      # Create node
      node = TextNode(text=prepared_text,
                      metadata=metadata,
                      embedding=embedding)

      # Insert the node
      await asyncio.get_event_loop().run_in_executor(
          self.executor, lambda: self.log_index.insert_nodes([node]))

      print(
          f"Successfully upserted log for chat_session_id {log.chat_session_id}"
      )
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
                          "date_updated": datetime.now().timestamp()
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
                                 remove_stopwords=False,
                                 use_stemming=False,
                                 use_lemmatization=False):
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
