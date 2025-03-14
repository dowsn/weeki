from typing import AsyncGenerator, Optional
import json
import asyncio
from langchain_xai import ChatXAI

from app.models import User, Chat_Session, Message, Topic, Log, SessionTopic, SessionLog
from channels.db import database_sync_to_async
from .moment_manager import MomentManager
from typing import Union, Dict
from api.agents.models.conversation_models import ConversationState


class ConversationAgent:
  """
    Facade that orchestrates the conversation system and provides a simple interface 
    for the WebSocket consumer
    """

  def __init__(self, user: User, chat_session: Chat_Session, ws_consumer):
    """Initialize the conversation agent with required dependencies."""
    self.user = user
    self.chat_session = chat_session
    self.ws_consumer = ws_consumer
    self.ai_model = None
    self.moment_manager = None

  @classmethod
  async def create(cls, user: User, chat_session: Chat_Session, ws_consumer):
    """Factory method to create and initialize a ConversationAgent instance."""
    instance = cls(user, chat_session, ws_consumer)
    instance.ai_model = ChatXAI(model="grok-2-1212", temperature=0.8)
    instance.moment_manager = MomentManager(
        user,
        chat_session,
        instance.ai_model,
        on_ending_soon=instance._handle_ending_soon,
        on_session_end=instance._handle_session_end)
    return instance

  async def run_agent(self, query: str,
                      agent_context: dict) -> ConversationState:
    """Run the agent with the given query and yield response tokens."""
    response = await self.moment_manager.run_agent(query, agent_context)
    await self._save_message("assistant", response.response)

    return response

  async def start_session(self) -> AsyncGenerator[str, None]:
    """Start a new session and yield the initial message tokens."""
    initial_message = await self.moment_manager.start_session()

    # Only save and yield tokens if there's an initial message
    if initial_message:

      # Check if initial_message has a content attribute
      message_text = initial_message.content if hasattr(
          initial_message, 'content') else str(initial_message)

      await self._save_message("assistant", message_text)

      # Split the message text into tokens
      for token in message_text.split():
        yield token + " "

  async def _handle_ending_soon(self, message: str) -> None:
    """Handle the ending soon event by sending tokens to websocket."""
    await self._save_message("assistant", message)
    for token in message.split():
      await self.ws_consumer.send(text_data=json.dumps({
          'type': 'token',
          'token': token + " "
      }))
      await asyncio.sleep(0.01)  # Small delay

  async def update_chat_session(self, state):
    remaining_time = await self.moment_manager.get_remaining_time()
    self.chat_session.time_left = remaining_time
    self.chat_session.potential_topic = state.potential_topic
    self.chat_session.chars_since_check = state.chars_since_check
    self.chat_session.saved_query = state.saved_query
    print("potential_topic", self.chat_session.potential_topic)
    print("chat_session updated", self.chat_session)
    await database_sync_to_async(self.chat_session.save)()

  async def save_session_state(self):
    """
    Save the current conversation state to the database using the SessionTopic
    and SessionLog association models for better data organization and retrieval
    """
    # Get current state and remaining time
    current_state = self.moment_manager.get_current_state()
    remaining_time = await self.moment_manager.get_remaining_time()

    # Update basic session fields
    await database_sync_to_async(
        lambda: self.update_chat_session(current_state))()

    # Prepare lists for bulk operations
    session_topics = []
    session_logs = []

    # Process cached topics
    @database_sync_to_async
    def process_cached_topics():
      # Clear existing cached topic associations for this session
      SessionTopic.objects.filter(
          session=self.chat_session,
          status=1  # Cache status
      ).delete()

      # Create new associations for cached topics
      for cached_topic in current_state.cached_topics:
        topic, _ = Topic.objects.get_or_create(name=cached_topic.name,
                                               user=self.user,
                                               defaults={
                                                   'description':
                                                   cached_topic.text,
                                                   'active': True
                                               })

        # Create new association
        SessionTopic.objects.create(
            session=self.chat_session,
            topic=topic,
            status=1,  # Cache status
            confidence=0.0 if remaining_time == 0 else cached_topic.confidence)

    # Process current topics
    @database_sync_to_async
    def process_current_topics():
      # Clear existing current topic associations for this session
      SessionTopic.objects.filter(
          session=self.chat_session,
          status=2  # Current status
      ).delete()

      # Create new associations for current topics
      for current_topic in current_state.current_topics:
        topic, _ = Topic.objects.get_or_create(name=current_topic.name,
                                               user=self.user,
                                               defaults={
                                                   'description':
                                                   current_topic.text,
                                                   'active': True
                                               })

        # Create new association
        SessionTopic.objects.create(
            session=self.chat_session,
            topic=topic,
            status=2,  # Current status
            confidence=0.0
            if remaining_time == 0 else current_topic.confidence)

    # Process current logs
    # fixxxx
    @database_sync_to_async
    def process_cached_logs():
      # Clear existing cached log associations for this session
      SessionLog.objects.filter(session=self.chat_session).delete()

      # Create new associations for cached logs
      for cached_log in current_state.cached_logs:

        topic = Topic.objects.get(name=cached_log.topic_id)
        
        log, _ = Log.objects.get_or_create(
          user=self.user,
          chat_session=self.chat_session,
          topic=topic,
          defaults={'text': cached_log.text})

        # Create new association
        SessionLog.objects.create(
            session=self.chat_session,
            log=log,
            status=1,  # Cache status
           )
      
    
    @database_sync_to_async
    def process_current_logs():

      for current_log in current_state.current_logs:
        # First, find the topic
        topic = Topic.objects.get(id=current_log.topic_id)

        # Create or get the log
        log, _ = Log.objects.get_or_create(
            user=self.user,
            chat_session=self.chat_session,
            topic=topic,
            defaults={'text': current_log.text})

        # Create association
        SessionLog.objects.create(
            session=self.chat_session,
            log=log,
            status=2  # Cache status
        )

    # Execute all database operations
    await process_cached_topics()
    await process_current_topics()
    await process_cached_logs()
    await process_current_logs()

  async def _handle_session_end(self, message: str) -> None:
    """Handle the session end event by sending tokens and closing connection."""
    await self._save_message("assistant", message)
    for token in message.split():
      await self.ws_consumer.send(text_data=json.dumps({
          'type': 'token',
          'token': token + " "
      }))
      await asyncio.sleep(0.01)  # Small delay
    await self.ws_consumer.handle_close()

  async def _save_message(self, role: str, content: str) -> None:

    await database_sync_to_async(Message.objects.create
                                 )(chat_session=self.chat_session,
                                   content=content,
                                   role=role)
