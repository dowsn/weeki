from typing import Optional
import json
import asyncio

from app.models import User, Chat_Session, Message
from channels.db import database_sync_to_async
from .moment_manager import MomentManager
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
    # Use Django's update() for faster database operation
    @database_sync_to_async
    def update_time_left():
      Chat_Session.objects.filter(id=self.chat_session.id).update(time_left=remaining_time)
    
    # Update local instance and database
    self.chat_session.time_left = remaining_time
    await update_time_left()

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
    print("DEBUG: Starting save_session_state")
    
    # Get current state and remaining time
    try:
      print("DEBUG: Getting current state")
      current_state = self.moment_manager.get_current_state()
      print("DEBUG: Getting remaining time")
      remaining_time = await self.moment_manager.get_remaining_time()
      print(f"DEBUG: Got remaining time: {remaining_time}")

      if complete:
        remaining_time = 0
        print("DEBUG: Set remaining time to 0 for complete session")

      # Update basic session fields - fail fast if there's an issue
      print("DEBUG: About to update chat session")
      try:
        await self.update_chat_session(current_state, remaining_time)
        print("DEBUG: Chat session updated successfully")
      except Exception as e:
        print(f"ERROR: update_chat_session failed: {e}")
        # Continue anyway - don't let this block the end session
        
    except Exception as e:
      print(f"ERROR: save_session_state failed: {e}")
      # Don't let this prevent the session from ending



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
