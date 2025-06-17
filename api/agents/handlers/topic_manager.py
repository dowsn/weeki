from api.agents.models.conversation_models import ConversationState, TopicState
from typing import List
from app.models import Conversation_Session, SessionTopic, Topic
from channels.db import database_sync_to_async
from llama_index.core import Settings

import numpy as np
from api.agents.handlers.pinecone_manager import PineconeManager


class TopicManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.similarity_threshold = 0.7
    self.confidence_threshold = 0.5
    self.pinecone_manager = pinecone_manager
    self.embedding_model = Settings.embed_model

  async def store_topic(self, topic: TopicState,
                        state: ConversationState) -> TopicState:

    @database_sync_to_async
    def create_topic_in_db():
      topic_in_db = Topic.objects.create(name=topic.topic_name,
                                         description=topic.text,
                                         user_id=state.user_id)

      SessionTopic.objects.create(
          session_id=state.chat_session_id,
          topic_id=topic_in_db.pk,  # Note: use topic_in_db.pk here
          status=1,
          confidence=0.85)

      return topic_in_db

    topic_in_db = await create_topic_in_db()

    topic.topic_id = topic_in_db.pk

    print("new_topic_state", topic.topic_name)
    print("new_topic_id", topic.topic_id)

    # Use pinecone_manager to create and store the embedding
    embedding = await self.pinecone_manager.upsert_topic(topic)
    topic.embedding = embedding

    return topic

  async def check_topics(self, state: ConversationState) -> ConversationState:
    state.current_topics = []
    matched_topics = []

    print(f"🔧 DEBUG: state.embedding = {state.embedding}")
    print(f"🔧 DEBUG: type(state.embedding) = {type(state.embedding)}")
    print(f"🔧 DEBUG: embedding is None? {state.embedding is None}")
    print(f"🔧 DEBUG: embedding is empty list? {state.embedding == []}")

    if state.embedding:
      print("🔍 TOPIC RETRIEVAL: Starting topic search process")
      print(f"📊 EMBEDDING INFO: Vector length = {len(state.embedding)}")

      # Debug what's stored first
      # await self.pinecone_manager.debug_what_is_stored()

      # Try retrieval with very low threshold

      if state.embedding:
        print(f"✅ FIRST CHECK: State embedding exists - {len(state.embedding)} dimensions")

      print("🎯 RETRIEVING: Querying Pinecone for similar topics...")
      new_topics = await self.pinecone_manager.retrieve_topics(
          embedding=state.embedding,
          base_threshold=0.3,  # Must be semantically relevant
          final_threshold=0.5,  # Must pass final quality check
          max_results=3)  # Maximum 3 topics
      matched_topics = new_topics
      print(f"📦 RETRIEVED: Found {len(matched_topics)} matching topics from vector DB")

    state.current_topics = matched_topics
    print(f"🎪 FINAL RESULT: {len(matched_topics)} topics matched for current conversation")
    for topic in matched_topics:
      print(f"  📌 {topic.topic_name} (confidence: {topic.confidence:.3f})")
    
    # Create SessionTopic entries for matched existing topics
    if matched_topics:
      await self._create_session_topic_entries(state.chat_session_id, matched_topics)

    if len(matched_topics) == 0:
      print("🆕 NEW TOPIC: No matching topics found - will create new topic")
      state = await self.create_new_topic(state)

    state.embedding = None

    return state

  async def _create_session_topic_entries(self, session_id: int, topics: List[TopicState]):
    """Create SessionTopic entries for existing topics if they don't already exist"""
    @database_sync_to_async
    def create_entries():
      for topic in topics:
        # Check if SessionTopic entry already exists
        existing = SessionTopic.objects.filter(
          session_id=session_id,
          topic_id=topic.topic_id
        ).exists()
        
        if not existing:
          SessionTopic.objects.create(
            session_id=session_id,
            topic_id=topic.topic_id,
            status=1,  # Active status
            confidence=topic.confidence
          )
          print(f"Created SessionTopic entry for existing topic: {topic.topic_name}")
        else:
          print(f"SessionTopic entry already exists for: {topic.topic_name}")
    
    await create_entries()

  async def create_new_topic(self,
                             state: ConversationState) -> ConversationState:
    state.potential_topic = "NA"
    return state

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
      print("topic id", topic.id)
      embedding = await self.pinecone_manager.get_topic_vector_by_id(topic.id)

      topic_states.append(
          TopicState(topic_id=topic.id,
                     topic_name=topic.name,
                     text=topic.description,
                     confidence=st.confidence,
                     embedding=embedding,
                     date_updated=topic.date_updated))

    return topic_states
