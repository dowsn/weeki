from typing import AsyncGenerator, Optional
import json
import asyncio
from langchain_xai import ChatXAI

from app.models import User, Chat_Session, Message, Topic, Log, SessionTopic, SessionLog
from channels.db import database_sync_to_async
from .moment_manager import MomentManager
from typing import Union, Dict
from api.agents.models.conversation_models import ConversationState
from langchain.chat_models import init_chat_model


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
    instance.ai_model = init_chat_model(model="xai:grok-3-mini-fast",
                                        configurable_fields="any",
                                        config_prefix="foo",
                                        temperature=0.7,
                                        reasoning_effort="high")

    instance.moment_manager = MomentManager(
        user,
        chat_session,
        instance.ai_model,
        stream_message=instance.stream_message,
        ws_consumer=ws_consumer)
    return instance

  def is_session_ended(self):
    """Check if session has ended due to time"""
    return self.moment_manager.is_session_ended()

  async def run_agent(self, query: str,
                      agent_context: dict) -> ConversationState:
    """Run the agent with the given query and yield response tokens."""
    response = await self.moment_manager.run_agent(query, agent_context)

    # save
    await self.save_message("assistant", response.response)

    return response

  async def start_session(self):
    """Start a new session and yield the initial message tokens."""
    initial_message = await self.moment_manager.start_session()

    # Only save and yield tokens if there's an initial message
    if initial_message:

      # Split the message text into tokens
      await self.save_message("assistant", initial_message, show_in=False)
      return initial_message

  async def stream_message(self, message: str) -> None:
    """Handle time-based messages by sending tokens to websocket."""

    # Check for end signal hash
    END_HASH = "2458792345u01298347901283491234"

    if END_HASH in message:
      print("End signal detected in stream_message")
      # Remove the hash from the message
      clean_message = message.replace(END_HASH, "").strip()
      # Trigger close with the clean message
      await self.ws_consumer.handle_close(complete=True, message=clean_message)
      return

    # Regular message handling
    await self.save_message("assistant", message, show_in=False)
    await self.ws_consumer.stream_tokens(message,
                                         message_type="automatic_message")

  async def _handle_ending_soon(self, message: str) -> None:
    """Handle the ending soon event by sending tokens to websocket."""
    await self.save_message("assistant", message, show_in=False)
    for token in message.split():
      token_with_space = token + " "
      await self.ws_consumer.send(text_data=json.dumps({
          'type': 'message',
          'text': token_with_space
      }))
      await asyncio.sleep(0.01)  # Small delay

  async def update_chat_session(self, state, remaining_time):

    self.chat_session.time_left = remaining_time

    # self.chat_session.potential_topic = state.potential_topic
    # self.chat_session.chars_since_check = state.chars_since_check
    # self.chat_session.saved_query = state.saved_query
    # Fix: Create a proper async wrapper for the save method
    @database_sync_to_async
    def save_chat_session():
      self.chat_session.save()

    # Call the wrapped function
    await save_chat_session()

  async def end_session(self) -> str:
    """End the session and return any final message (without streaming it)."""
    response = await self.moment_manager.end_session()

    # Save the message to the database (without hash)
    if response:
      clean_response = response.replace("2458792345u01298347901283491234",
                                        "").strip()
      await self.save_message("assistant", clean_response, show_in=False)

    return clean_response if response else ""

  async def save_session_state(self, complete: bool):
    """
    Save the current conversation state to the database using the SessionTopic
    and SessionLog association models for better data organization and retrieval
    """
    # Get current state and remaining time

    current_state = self.moment_manager.get_current_state()
    remaining_time = await self.moment_manager.get_remaining_time()

    if complete:
      remaining_time = 0

    # Update basic session fields
    await self.update_chat_session(current_state, remaining_time)

    # # Prepare lists for bulk operations
    # session_topics = []
    # session_logs = []

    # # Process cached topics
    # @database_sync_to_async
    # def process_cached_topics():
    #   # Clear existing cached topic associations for this session
    #   SessionTopic.objects.filter(
    #       session=self.chat_session,
    #       status=1  # Cache status
    #   ).delete()

    #   print("processing cached topics")

    #   # Create new associations for cached topics
    #   for cached_topic in current_state.cached_topics:
    #     print("Caa")
    #     print("cached_topic", cached_topic.name)
    #     topic, _ = Topic.objects.get_or_create(name=cached_topic.name,
    #                                            user=self.user,
    #                                            defaults={
    #                                                'description':
    #                                                cached_topic.text,
    #                                                'active': True
    #                                            })

    #     # Create new association
    #     SessionTopic.objects.create(
    #         session=self.chat_session,
    #         topic=topic,
    #         status=1,  # Cache status
    #         confidence=0.0 if remaining_time == 0 else cached_topic.confidence)

    # # Process current topics
    # @database_sync_to_async
    # def process_current_topics():
    #   # Clear existing current topic associations for this session
    #   SessionTopic.objects.filter(
    #       session=self.chat_session,
    #       status=2  # Current status
    #   ).delete()

    #   # Create new associations for current topics
    #   for current_topic in current_state.current_topics:
    #     topic, _ = Topic.objects.get_or_create(name=current_topic.name,
    #                                            user=self.user,
    #                                            defaults={
    #                                                'description':
    #                                                current_topic.text,
    #                                                'active': True
    #                                            })

    #     # Create new association
    #     SessionTopic.objects.create(
    #         session=self.chat_session,
    #         topic=topic,
    #         status=2,  # Current status
    #         confidence=0.0
    #         if remaining_time == 0 else current_topic.confidence)

    # # Process current logs
    # # fixxxx
    # @database_sync_to_async
    # def process_cached_logs():
    #   # Clear existing cached log associations for this session
    #   SessionLog.objects.filter(session=self.chat_session).delete()

    #   # Create new associations for cached logs
    #   for cached_log in current_state.cached_logs:

    #     topic = Topic.objects.get(name=cached_log.topic_id)

    #     log, _ = Log.objects.get_or_create(user=self.user,
    #                                        chat_session=self.chat_session,
    #                                        topic=topic,
    #                                        defaults={'text': cached_log.text})

    #     # Create new association
    #     SessionLog.objects.create(
    #         session=self.chat_session,
    #         log=log,
    #         status=1,  # Cache status
    #     )

    # @database_sync_to_async
    # def process_current_logs():

    #   for current_log in current_state.current_logs:
    #     # First, find the topic
    #     topic = Topic.objects.get(id=current_log.topic_id)

    #     # Create or get the log
    #     log, _ = Log.objects.get_or_create(user=self.user,
    #                                        chat_session=self.chat_session,
    #                                        topic=topic,
    #                                        defaults={'text': current_log.text})

    #     # Create association
    #     SessionLog.objects.create(
    #         session=self.chat_session,
    #         log=log,
    #         status=2  # Cache status
    #     )

    # # Execute all database operations
    # await process_cached_topics()
    # await process_current_topics()
    # await process_cached_logs()
    # await process_current_logs()

  # async def stream_message(self,
  #                          message: str,
  #                          is_final_timeout: bool = False) -> None:
  #   """Handle the ending soon event by sending tokens to websocket."""
  #   await self._save_message("assistant", message)

  #   # Use different method if this is a final timeout message
  #   if is_final_timeout:
  #     await self.ws_consumer.stream_final_timeout_message(message)
  #   else:
  #     await self.ws_consumer.stream_tokens(message)

  async def get_end_message(self) -> str:
    """Get the final end session message without any side effects"""
    response = await self.moment_manager.end_session()

    await self.save_message("assistant", response, show_in=False)

    return response

  async def save_message(self,
                         role: str,
                         content: str,
                         show_in: Optional[bool] = None) -> None:
    current_state = self.moment_manager.get_current_state()

    # Use provided show_in if specified, otherwise use the current logic
    display_flag = show_in if show_in is not None else (
        current_state.saved_query == "")

    await database_sync_to_async(Message.objects.create
                                 )(chat_session=self.chat_session,
                                   content=content,
                                   role=role,
                                   show_in=display_flag)
