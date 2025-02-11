# moment_manager.py
from typing import AsyncGenerator
from datetime import datetime
from langchain_xai import ChatXAI
from api.agents.models.conversation_models import ConversationState
from app.models import Chat_Session, Message, Profile
from channels.db import database_sync_to_async
from api.agents.graph.graph_conversation import ConversationGraphManager
from api.agents.handlers.time_manager import TimeManager
from api.agents.handlers.topic_manager import TopicManager
from api.agents.handlers.log_manager import LogManager
from api.agents.handlers.session_manager import SessionManager
from django.contrib.auth.models import User
from api.agents.handlers.pinecone_manager import PineconeManager


class MomentManager:

  def __init__(self, user: User, chat_session: Chat_Session, ai_model: ChatXAI,
               on_ending_soon, on_session_end):
    self.user = user
    self.chat_session = chat_session
    self.ai_model = ai_model
    self.messages = []
    self.remaining_minutes = getattr(self.chat_session, 'time_left')

    self.on_ending_soon = on_ending_soon
    self.on_session_end = on_session_end

    self.pinecone_manager = PineconeManager()
    self.topic_manager = TopicManager(self.pinecone_manager)
    self.log_manager = LogManager(self.pinecone_manager)

    self.state = self._initialize_state()
    self.time_manager = TimeManager(self.remaining_minutes,
                                    self._on_time_update)
    self.session_manager = SessionManager(getattr(self.chat_session, 'first'),
                                          ai_model)
    self.graph = self._setup_graph()

  def _initialize_state(self) -> ConversationState:
    messages_str = self._format_message_history()

    return ConversationState(
        # fix
        user_id=self.user.id,
        username=self.user.username,
        conversation_context=messages_str,
    )

  def get_current_state(self) -> ConversationState:
    return self.state

  def _setup_graph(self):
    return ConversationGraphManager(ai_model=self.ai_model,
                                    topic_manager=self.topic_manager,
                                    log_manager=self.log_manager).graph

    async def get_one_topic(self, topic: Topic, get_embedding: Bool = True) -> TopicState:
      """Convert Topic model to TopicState"""
      if topic is None:
          return None

      if get_embedding:
          embedding = await self.pinecone_manager.get_embedding(topic.name)
      else:
          embedding=None
      

      return TopicState(
          name=topic.name,
          description=topic.description,
          confidence=topic.confidence,
          embedding=embedding,
          date_updated=topic.date_updated
      )

    async def load_topics(self):
      """Load all types of topics from database into state"""

      # Load cached topics
      cached_topics = await database_sync_to_async(
          lambda: list(Topic.objects.filter(
              user=self.user,
              currrent_session_status=1
          ))
      )()

      self.state.cached_topics = []
      for topic in cached_topics:
          topic_state = await self.get_one_topic(topic)
          if topic_state:
              self.state.cached_topics.append(topic_state)

      # Load current topics
      current_topics = await database_sync_to_async(
          lambda: list(Topic.objects.filter(
              user=self.user,
              currrent_session_status=2
          ))
      )()

      self.state.current_topics = []
      for topic in current_topics:
          topic_state = await self.get_one_topic(topic)
          if topic_state:
              self.state.current_topics.append(topic_state)

      # Load potential topic (inactive)
      potential_topic = await database_sync_to_async(
          lambda: Topic.objects.filter(
              user=self.user,
              active=False
          ).first()
      )()

      self.state.potential_topic = await self.get_one_topic(potential_topic, get_one_topic=False)

      # Load chars since check
      self.state.chars_since_check = self.chat_session.chars_since_check

  def _format_message_history(self) -> str:

    last_role = None
    formatted = ""
    for msg in self.messages:
      role = 'Human' if msg['role'] == 'user' else 'Assistant'
      if last_role == role:
        formatted += f"{msg['content']}\n"
      else:
        formatted += f"{role}: {msg['content']}\n"
      last_role = role
    return formatted

  async def load_messages(self):
    self.messages = await database_sync_to_async(
        Message.objects.filter(
            chat_session=self.chat_session).order_by('date_created'))()
    self.state.conversation_context = self._format_message_history()

  async def load_character(self):
    profile = database_sync_to_async(Profile.objects.get(user=self.user))

    # fix
    self.state.character = profile.character

  async def _on_time_update(self, elapsed_minutes: int):
    self.remaining_minutes -= elapsed_minutes

    if self.remaining_minutes == 5:
      message = await self.session_manager.handle_ending_soon()
      if self.on_ending_soon:
        await self.on_ending_soon(message)

    elif self.remaining_minutes == 0:
      message = await self.session_manager.handle_end()
      if self.on_session_end:
        await self.on_session_end(message)

  async def run_agent(self, query: str) -> str:
    self.state.add_message(query)
    # Run through process_message node and update internal state
    result = await self.graph.arun(self.state, "start")
    self.state = result  # Ensure state is updated with graph changes
    return result.get_response()

# initialize state and first message

  async def start_session(self):
    await self.time_manager.start_monitoring()
    await self.load_messages()
    await self.load_character()
    await self.load_topics()

    return await self.session_manager.handle_start()

  def get_remaining_time(self) -> int:
    return self.time_manager.get_remaining_time()

  async def end_session(self):
    self.time_manager.stop_monitoring()
    await self.graph.arun(self.state, "handle_end")
    return await self.session_manager.handle_end()
