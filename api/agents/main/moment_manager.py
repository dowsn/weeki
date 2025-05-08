# moment_manager.py
from typing import AsyncGenerator
from datetime import datetime
from langchain_xai import ChatXAI
from openai import BaseModel
from api.agents.handlers.conversation_helper import ConversationHelper
from api.agents.models.conversation_models import ConversationState, TopicState
from app.models import Chat_Session, Message, Profile, Topic
from channels.db import database_sync_to_async
from api.agents.graph.graph_conversation import ConversationGraphManager
from api.agents.handlers.time_manager import TimeManager
from api.agents.handlers.topic_manager import TopicManager
from api.agents.handlers.log_manager import LogManager
from api.agents.handlers.session_manager import SessionManager
from django.contrib.auth.models import User
from api.agents.handlers.pinecone_manager import PineconeManager
from datetime import timedelta
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel


class MomentManager:

  def __init__(self, user, chat_session: Chat_Session, ai_model,
               stream_message):
    self.user = user
    self.chat_session = chat_session
    self.ai_model = ai_model
    self.messages = []
    self.remaining_minutes = getattr(self.chat_session, 'time_left')
    print(f"Remaining minutes: {self.remaining_minutes}")

    self.stream_message = stream_message
    self.converstation_helper = ConversationHelper(ai_model=self.ai_model)
    self.pinecone_manager = PineconeManager(user_id=self.user.id)
    self.topic_manager = TopicManager(self.pinecone_manager)
    self.log_manager = LogManager(self.pinecone_manager)


    self.state: ConversationState = self._initialize_state()
    self.time_manager: TimeManager = TimeManager(
        chat_session=self.chat_session,
        remaining_minutes=self.remaining_minutes,
        on_time_update=self._on_time_update)
    self.session_manager: SessionManager = SessionManager(
        self.chat_session, self.pinecone_manager, self.topic_manager,
        self.log_manager, self.ai_model, self.converstation_helper)

    self.graph: ConversationGraphManager = self._setup_graph()

  def _initialize_state(self) -> ConversationState:

    return ConversationState(chat_session_id=self.chat_session.pk,
                             user_id=int(self.user.id),
                             username=str(self.user.username),
                             conversation_context='')

  def get_current_state(self) -> ConversationState:
    return self.state

  def _setup_graph(self):
    return ConversationGraphManager(
        ai_model=self.ai_model,
        topic_manager=self.topic_manager,
        log_manager=self.log_manager,
        conversation_helper=self.converstation_helper).graph

  # async def load_topics_and_logs(self):
  #   """
  #   Load all types of topics from database into state using the new
  #   association models for better data organization and retrieval
  #   """
  #   # Load active topics list for new sessions
  #   if len(self.messages) == 0:

  #     @database_sync_to_async
  #     def get_active_topics():
  #       return list(
  #           Topic.objects.filter(user=self.user,
  #                                date_updated__gte=datetime.now() -
  #                                timedelta(days=90),
  #                                active=True).values_list('name', flat=True))

  #     topics_list = await get_active_topics()
  #     self.state.active_topics = ", ".join(topics_list)

  #   # Load cached topics (status=1) using topic manager
  #   self.state.cached_topics = await self.topic_manager.get_session_topics(
  #       session_id=self.chat_session.id,
  #       status=1  # Cache status
  #   )

  #   # Load current topics (status=2) using topic manager
  #   self.state.current_topics = await self.topic_manager.get_session_topics(
  #       session_id=self.chat_session.id,
  #       status=2  # Current status
  #   )

  #   # Load logs using log manager
  #   self.state.cached_logs = await self.log_manager.get_session_logs(
  #       session_id=self.chat_session.id,
  #       status=1  # Cache status
  #   )

  #   self.state.current_logs = await self.log_manager.get_session_logs(
  #       session_id=self.chat_session.id,
  #       status=2  # Cache status
  #   )

  #   # Load potential topic from session
  #   self.state.potential_topic = self.chat_session.potential_topic

  #   # Load chars since check
  #   self.state.chars_since_check = self.chat_session.chars_since_check

  def _format_message_history(self) -> str:

    last_role = None
    formatted = ""
    for msg in self.messages:
      role = 'Human' if msg.role == 'user' else 'Assistant'
      if last_role == role:
        formatted += f"{msg.content}\n"
      else:
        formatted += f"{role}: {msg.content}\n"
      last_role = role
    return formatted

  async def load_messages(self):

    def get_messages():
      return list(
          Message.objects.filter(
              chat_session=self.chat_session).order_by('date_created'))

    self.messages = await database_sync_to_async(get_messages)()

    print(f"Loaded {len(self.messages)} messages")
    self.state.conversation_context = self._format_message_history()

  async def load_character(self):

    def get_profile():
      return Profile.objects.filter(user=self.user).first()

    profile = await database_sync_to_async(get_profile)()

    # fix
    self.state.character = profile.character

  async def _on_time_update(self, elapsed_minutes: int):
    self.remaining_minutes -= elapsed_minutes

    if self.remaining_minutes == 5:
      print("ending soo")
      message = await self.session_manager.handle_ending_soon()
      print('message', message)
      if self.stream_message:
        await self.stream_message(message)

    elif self.remaining_minutes == 0:
      message = await self.session_manager.handle_end()
      if self.stream_message:
        await self.stream_message(message)

  async def run_agent(self, query: str,
                      agent_context: dict) -> ConversationState:
    print(f"Original query: {query}")

    self.state.add_context(agent_context)
    print(self.state.confirm_topic)
    self.state.add_message(query)

    # Add logging before graph invocation
    print(
        f"State before graph invoke: prompt_query = {self.state.prompt_query}")
    print(
        f"State before graph invoke: potential_topic = {self.state.potential_topic}"
    )

    # Run through the graph and get the updated state
    result = await self.graph.ainvoke(self.state)
    print(f"Graph execution completed, result type: {type(result)}")

    # Ensure we have a proper ConversationState object
    if isinstance(result, dict):
      print("Converting dict result to ConversationState")
      try:

        result = ConversationState(**dict(result))
      except Exception as e:
        print(f"Error converting result to ConversationState: {str(e)}")
        # If conversion fails, just use the dict directly
        pass

    # Update our state with the result
    self.state = result

    # Update the chat session with current state values
    await self._update_chat_session_state()

    if isinstance(self.state, ConversationState):
      return self.state
    else:
      raise TypeError("Unexpected state type. Expected 'ConversationState'.")

  async def _update_chat_session_state(self):
    """Update the chat session with current state values"""
    updates = {
        'potential_topic': getattr(self.state, 'potential_topic', ""),
        'saved_query': getattr(self.state, 'saved_query', ""),
    }

    @database_sync_to_async
    def update_session():
      for field, value in updates.items():
        setattr(self.chat_session, field, value)
      self.chat_session.save(update_fields=list(updates.keys()))

    await update_session()


# initialize state and first message

  async def load_previous_session(self):

    last_chat_session = await database_sync_to_async(
        lambda: Chat_Session.objects.filter(user=self.user, time_left=0
                                            ).order_by('-id').first())()

    if last_chat_session:
      self.state.previous_summary = last_chat_session.summary

  async def start_session(self):
    await self.time_manager.start_monitoring()
    await self.load_messages()
    await self.load_previous_session()

    if not self.messages:
      self.session_manager.update_state(self.state)
      return await self.session_manager.handle_start()
    return ""

  async def get_remaining_time(self) -> int:
    remaining_time = await self.time_manager.get_remaining_time()
    return int(remaining_time)

  async def end_session(self):
    self.time_manager.stop_monitoring()
    # Update session manager with final state
    self.session_manager.update_state(self.state)
    await self.session_manager.handle_state_end()
    response = await self.session_manager.handle_end()
    # tady spaces
    response = response.strip()
    print("end response", response)
    return response
