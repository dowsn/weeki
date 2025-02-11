from typing import AsyncGenerator, Optional
import json
import asyncio
from langchain_xai import ChatXAI

from app.models import User, Chat_Session, Message
from channels.db import database_sync_to_async
from .moment_manager import MomentManager


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
          on_session_end=instance._handle_session_end
      )
      return instance

  async def run_agent(self, query: str) -> AsyncGenerator[str, None]:
    """Run the agent with the given query and yield response tokens."""
    response = await self.moment_manager.run_agent(query)
    await self._save_message("assistant", response)
    for token in response.split():
      yield token + " "

  async def start_session(self) -> AsyncGenerator[str, None]:
    """Start a new session and yield the initial message tokens."""
    initial_message = await self.moment_manager.start_session()
    await self._save_message("assistant", initial_message)
    for token in initial_message.split():
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

  async def update_chat_session(self, chars_since_check):
    remaining_time = self.moment_manager.get_remaining_time()
    self.chat_session.time_left = remaining_time
    self.chat_session.chars_since_check = chars_since_check
    self.chat_session.save()

  async def save_session_state(self):
    # update session time

    current_state = self.moment_manager.get_current_state()
    remaining_time = self.moment_manager.get_remaining_time()
    
    await database_sync_to_async(self.update_chat_session(current_state.chars_since_check))()

    # Save potential topic
    if current_state.potential_topic:
        await database_sync_to_async(Topic.objects.create)(
            name=current_state.potential_topic.name,
            description=current_state.potential_topic.description,
            confidence=current_state.potential_topic.confidence,
            user=self.user,
            active=False,
            currrent_session_status=0  # No status for potential
        )

    # Update cached topics
    for cached_topic in current_state.cached_topics:
        await database_sync_to_async(Topic.objects.filter(
            name=cached_topic.name,
            user=self.user
        ).update)(
            confidence=0.0 if remaining_time == 0 else cached_topic.confidence,
            currrent_session_status=1  # Cache status
        )

    # Update current topics
    for current_topic in current_state.current_topics:
        await database_sync_to_async(Topic.objects.filter(
            name=current_topic.name,
            user=self.user
        ).update)(
            confidence=0.0 if remaining_time == 0 else current_topic.confidence,
            currrent_session_status=2  # Current status
        )
  
 
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
    """Save a message to the database."""
    await database_sync_to_async(Message.objects.create
                                 )(chat_session=self.chat_session,
                                   content=content,
                                   role=role)

  # async def _save_chat_session(self) -> None:
  #   """Save the chat session to the database."""
  #   await database_sync_to_async(Chat_Session.objects.filter


# async def __init__(self, user: User, chat_session: Chat_Session):
#   self.xai_model = ChatXAI(model="grok-2-1212", temperature=0.8)
#   self.user = user
#   self.chat_session = chat_session
#   self.conversation_manager = ConversationManager(
#       user=user,
#       chat_session=chat_session,
#       xai_model=self.xai_model
#   )
#   self.messages = await self._load_messages()

#   self.conversation_window = 12

#   # self.topic_handlers = TopicHandlers(self.xai_model)

#   # Initialize graph
#   self.graph_manager = ConversationGraphManager(
#       agent=self
#   )

#   # Initialize state
#   self.state = self._initialize_state(
#       username=self.user.username,
#       user_id=user_id,
#       chat_session_id=chat_session_id,
#       messages=self.messages
#   )

# def _initialize_state(self, username: str, user_id: int,
#                      chat_session_id: int, messages: list) -> ConversationState:
#     """Initialize conversation state"""
#     time_state = TimeState(
#         start_time=datetime.now(),
#         remaining_minutes=self.chat_session.time_left
#     )

#     return ConversationState(
#         username=username,
#         user_id=user_id,
#         chat_session_id=chat_session_id,
#   conversation_context=self._format_message_history(messages),
#         beginner=self.chat_session.first,
#         time_state=time_state,
#     )

# async def _load_messages(self):
#   return await database_sync_to_async(
#       Message.objects.filter(chat_session=self.chat_session).order_by('date_created')
#   )()

# @staticmethod
# def _format_message_history(messages: list) -> str:
#     """Format message history for context"""
#     last_role = None
#     formatted_messages = ""
#     for msg in messages:
#         role = 'Human' if msg['role'] == 'user' else 'Assistant'
#         if last_role == role:
#             # If the same role as last message, just append content with \n
#             formatted_messages += f"{msg['content']}"
#         else:
#             # Otherwise, append a new formatted message
#             formatted_messages += f"{role}: {msg['content']}"
#         formatted_messages += "\n"
#         last_role = role

# async def process_message(self, query: str) -> AsyncGenerator[str, None]:
#     """
#     Main entry point for processing messages from WebSocket consumer.
#     Yields response tokens for streaming.
#     """

#     self.state.time_state.remaining_minutes = (
#         await self.time_service.get_remaining_time()
#     )

#     # Update state with new message
#     self.state.conversation_context += f"Human: {query}\n"

#     # Run through graph
#     result = await self.graph_manager.graph.run(self.state)

#     # Stream response back
#     response = result.conversation_context.split("\n")[-1].replace("Assistant: ", "")

#     await self.save_message(role="assistant", content=response)

#     for token in response.split():
#         yield token + " "

# async def save_message(self, role: str, content: str):
#   await database_sync_to_async(Message.objects.create)(
#       chat_session=self.chat_session,
#       content=content,
#       role=role
#   )

#   async def start_session(self) -> AsyncGenerator[str, None]:
#     initial_message = await self.conversation_manager.start_session()
#     await self._save_message("assistant", initial_message)
#     for token in initial_message.split():
#         yield token + " "

#     await self.save_message(role="assistant", content=initial_message)

# async def end_session(self) -> AsyncGenerator[str, None]:
#     """Handle session end gracefully"""
#     final_state = await self.session_handlers.handle_session_end(self.state)
#     response = final_state.conversation_context.split("\n")[-1].replace("Assistant: ", "")

#     for token in response.split():
#         yield token + " "
