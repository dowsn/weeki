from channels.generic.websocket import AsyncWebsocketConsumer
from api.agents.main.conversation_agent import ConversationAgent
import json
from app.models import User, Topic, Message, Chat_Session
from channels.db import database_sync_to_async
import asyncio
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from .serializers.chat_serializer import MessageSerializer
from typing import List, Dict, Any
from .services import get_chat_messages
# also add upsert pinecone


class ChatConsumer(AsyncWebsocketConsumer):

  async def connect(self):

    print("ChatConsumer.connect() called")
    self.close_code = None  # Initialize close code
    self.sending_final_message = False  # Flag to prevent premature closing
    self.should_close_after_final_message = False  # Flag for timeout-triggered closure

    self.is_connected = False

    # Get chat_session from URL params
    self.chat_session_id = self.scope['url_route']['kwargs'].get(
        'chat_session')

    # Extract token from query string
    query_string = self.scope['query_string'].decode()

    from urllib.parse import parse_qs
    query_params = parse_qs(query_string)

    token = None
    if 'token' in query_params:
      token = query_params['token'][0]

    # Validate token and get user_id
    if token:
      try:
        from rest_framework_simplejwt.tokens import AccessToken, TokenError
        token_obj = AccessToken(token)
        self.user_id = token_obj['user_id']
        print(f"Valid token for user_id: {self.user_id}")
      except TokenError as e:
        print(f"Token validation error: {str(e)}")
        # Send token expired error with specific code so client knows to refresh
        await self.close(code=4001)
        return
      except Exception as e:
        await self.close(code=4000)
        return
    else:
      await self.close(code=4001)
      return

    # Now fetch the user and chat session
    try:
      from django.db import models
      from app.models import User, Chat_Session
      from channels.db import database_sync_to_async

      self.user = await database_sync_to_async(User.objects.get
                                               )(id=self.user_id)

      self.chat_session = await database_sync_to_async(
          Chat_Session.objects.get)(id=self.chat_session_id, user=self.user)
    except User.DoesNotExist:
      await self.close(code=4002)
      return
    except Chat_Session.DoesNotExist:
      print()
      await self.close(code=4003)
      return
    except Exception as e:
      print(f"Unexpected error: {str(e)}")
      await self.close(code=4000)
      return

    # Accept the connection if everything is valid
    await self.accept()
    self.is_connected = True
    # GIVE AWAY

    # Create the agent after accepting connection

    await self.send_connection_status()

    print("Creating agent...")
    self.agent = await ConversationAgent.create(user=self.user,
                                                chat_session=self.chat_session,
                                                ws_consumer=self)

    self.first_message = await self.agent.start_session()

  async def send_connection_status(self):
    """Send connection status and message history"""
    try:
      # Fetch existing messages
      self.messages = await database_sync_to_async(lambda: list(
          Message.objects.filter(chat_session=self.chat_session).order_by(
              'date_created')))()

      # Convert messages to list of dicts
      message_data = [{
          'role': msg.role,
          'content': msg.content,
          'timestamp': msg.date_created.isoformat()
      } for msg in self.messages]

      # Send message history
      await self.send(
          text_data=json.dumps({
              'type': 'connection_status',
              'messages': message_data,
              'topics': self.chat_session.topic_names
          }))
    except Exception as e:
      print(f"Error sending connection status: {e}")

  @database_sync_to_async
  def get_latest_chat_session(self):
    """Get the most recent chat session for the current user"""
    try:
      user = User.objects.get(id=self.user_id)
      return Chat_Session.objects.filter(
          user=user).order_by('-date_created').first()
    except User.DoesNotExist:
      return None

  @database_sync_to_async
  def create_new_chat_session(self):
    """Create a new chat session for the current user"""
    user = User.objects.get(id=self.user_id)
    return Chat_Session.objects.create(
        user=user,
        title="New Conversation",  # Default title
        is_active=True)

  async def disconnect(self, close_code):
    print(f"Disconnecting with code: {close_code}")
    self.close_code = close_code  # Store the close code
    self.is_monitoring = False

    if hasattr(self, 'monitor_task'):
      self.monitor_task.cancel()
      try:
        await self.monitor_task
      except asyncio.CancelledError:
        pass

    # await self.handle_close(complete=False)

  async def receive(self, text_data):
    """CORRECTED VERSION with better end handling"""
    try:
      data = json.loads(text_data)
      print(f"Received data: {data}")
      message_type = data.get('type', '')

      # Handle connection_ready signal from frontend
      if message_type == 'connection_ready':
        print("Received connection_ready signal from frontend")
        if hasattr(self, 'first_message') and self.first_message:
          await self.stream_tokens(message=self.first_message,
                                   message_type="automatic_message",
                                   topics="")
        return

      query = data.get('query', '')

      if message_type == 'pause':
        print("Received pause signal")
        if hasattr(self, 'agent') and self.agent and hasattr(
            self.agent, 'moment_manager'):
          if hasattr(self.agent.moment_manager, 'time_manager'):
            self.agent.moment_manager.time_manager.pause_monitoring()
            await self.send(text_data=json.dumps({
                'type': 'timer_paused',
                'message': 'Timer paused'
            }))
        return

      # ✅ Handle resume signal
      if message_type == 'resume':
        print("Received resume signal")
        if hasattr(self, 'agent') and self.agent and hasattr(
            self.agent, 'moment_manager'):
          if hasattr(self.agent.moment_manager, 'time_manager'):
            self.agent.moment_manager.time_manager.resume_monitoring()
            await self.send(text_data=json.dumps({
                'type': 'timer_resumed',
                'message': 'Timer resumed'
            }))
        return

      # Handle close/end signals
      if message_type == 'close':
        print("Received close message")
        await self.handle_close(complete=False)
        return

      if message_type == 'end':
        print("Received end message")
        await self.handle_close(complete=True)
        return

      # Check if session has ended due to time
      if hasattr(self,
                 'agent') and self.agent.moment_manager.is_session_ended():
        await self.send(text_data=json.dumps(
            {
                'type': 'session_ended',
                'message': 'Session has ended due to time limit.'
            }))
        return

      if not query and message_type not in [
          'close', 'end', 'connection_ready'
      ]:
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': 'Empty query received'
        }))
        return

      if message_type == 'user':
        await self.agent.save_message('user', query)

      # Initialize agent_context
      agent_context = {}
      if message_type == 'topic_operation':
        agent_context['topic_confirmation'] = data.get('topic_confirmation', 2)

      # Acknowledge receipt of message
      await self.send(text_data=json.dumps({
          'type': 'status',
          'message': 'Processing your message'
      }))

      try:
        # Process messages that should trigger agent response
        if message_type in ["assistant", "topic_operation"]:
          # Get response from agent
          if self.agent is not None and not self.agent.moment_manager.is_session_ended(
          ):
            response = await self.agent.run_agent(query, agent_context)

            # Handle response
            if hasattr(response, 'response_type'):
              if response.response_type == "message":
                topics = response.topic_names if isinstance(
                    response.topic_names, str) else ""
                await self.stream_tokens(message=response.response,
                                         topics=topics,
                                         message_type="message")
              elif response.response_type == "topic":
                await self.stream_tokens(message=response.response,
                                         topics="No current topics",
                                         message_type="topic")

      except Exception as stream_error:
        print(f"Error during streaming: {str(stream_error)}")
        await self.send(text_data=json.dumps(
            {
                'type': 'error',
                'error': f'Streaming error: {str(stream_error)}'
            }))

    except json.JSONDecodeError as e:
      print(f"JSON decode error: {str(e)}")
      await self.send(text_data=json.dumps({
          'type': 'error',
          'error': 'Invalid message format'
      }))
    except Exception as e:
      print(f"Error processing message: {str(e)}")
      # Only send error if connection is still open
      if not getattr(self, 'close_code', None):
        try:
          await self.send(text_data=json.dumps({
              'type': 'error',
              'error': str(e)
          }))
        except Exception:
          # Connection already closed, ignore send error
          pass

  async def handle_close(self, complete: bool, message=""):
    """Simplified close handling with proper time manager cleanup"""

    if hasattr(self, '_closing') and self._closing:
      print("Already closing, ignoring duplicate close call")
      return

    self._closing = True
    print(
        f"handle_close called - complete: {complete}, has_message: {bool(message)}"
    )

    final_message = message

    try:
      if hasattr(self, 'agent') and self.agent is not None:
        # CRITICAL: Stop time monitoring IMMEDIATELY
        if hasattr(self.agent,
                   'moment_manager') and self.agent.moment_manager is not None:
          print("Stopping time manager from handle_close")
          self.agent.moment_manager.session_ended = True
          if hasattr(self.agent.moment_manager, 'time_manager'):
            self.agent.moment_manager.time_manager.stop_monitoring()

        # Save session state
        await self.agent.save_session_state(complete)

        # Only get end message if we don't already have one and we're completing
        if complete and not final_message:

          final_message = await self.agent.end_session()
          print(
              f"Got end message from agent: {final_message[:100] if final_message else 'None'}..."
          )

        # Stream the final message if we have one
        if final_message and self.is_connected:
          print("Streaming final message")
          await self.stream_tokens(final_message,
                                   message_type="automatic_message")

      # Only close the connection if this was an explicit close request
      # AND after we've finished streaming any messages
      # AND we're not currently sending a final message
      if not getattr(self, 'close_code', None) and not getattr(
          self, 'sending_final_message', False):

        print("Closing WebSocket connection...")
        await self.close(code=4000)

    except Exception as e:
      print(f"Error during close: {str(e)}")
      try:
        if self.is_connected:
          await self.send(
              text_data=json.dumps({
                  'type': 'error',
                  'error': f"Error during close: {str(e)}"
              }))
      except:
        pass
    finally:
      self._closing = False

  async def stream_tokens(self,
                          message: str,
                          topics: str = "",
                          message_type: str = "message"):
    """Helper method to stream tokens with proper format"""
    # Check if connection is still open before streaming
    if getattr(self, 'close_code', None):
      print("WebSocket already closed, skipping message streaming")
      return

    # Set flag to indicate we're sending a final message
    self.sending_final_message = True

    message = '*** ' + message
    # Split the message into tokens (words)
    tokens = message.split()

    # Iterate through tokens with their indices
    for i, token in enumerate(tokens):
      # Check connection state before each token
      if getattr(self, 'close_code', None):
        print("WebSocket closed during streaming, stopping")
        return

      token_with_space = token
      if i != 0:  # Add space to all tokens except the first one
        token_with_space = " " + token

      try:
        await self.send(text_data=json.dumps({
            'type': 'message',
            'text': token_with_space
        }))
        await asyncio.sleep(0.01)  # Small delay
      except Exception as e:
        print(f"Error sending token, connection likely closed: {e}")
        return

    # Send stream complete signal only if connection is still open
    try:
      await self.send(text_data=json.dumps({'type': 'stream_complete'}))
    except Exception as e:
      print(f"Error sending stream complete, connection likely closed: {e}")
    finally:
      # Clear the flag when we're done sending the final message
      self.sending_final_message = False

      # If this was a timeout-triggered final message, close the connection
      if hasattr(self, 'should_close_after_final_message'
                 ) and self.should_close_after_final_message:
        print("Closing connection after final timeout message")
        self.should_close_after_final_message = False
        try:
          await self.close(code=4000)
        except Exception as e:
          print(f"Error closing connection after final message: {e}")

  async def stream_final_timeout_message(self, message: str):
    """Stream final message when timeout occurs and then close connection"""
    self.should_close_after_final_message = True
    await self.stream_tokens(message)

    # ADD THIS CHECK - Check if connection is still active
    if not self.is_connected:
      print("Connection closed, stopping stream")
      return

    try:

      if message_type == "automatic_message":
        # ADD TRY-CATCH WRAPPER
        # Send signal for new message
        await self.send(text_data=json.dumps({
            'topics': topics,
            'type': 'new_message',
            'text': ''
        }))
        await asyncio.sleep(0.01)

      # Stream message character by character
      for char in message:
        if not self.is_connected:  # ADD THIS CHECK
          break

        await self.send(text_data=json.dumps({
            'topics': topics,
            'type': message_type,
            'text': char
        }))
        await asyncio.sleep(0.005)

      # Send completion signal
      if self.is_connected:  # ADD THIS CHECK
        await self.send(text_data=json.dumps({
            'type': 'stream_complete',
            'topics': topics,
            'text': ''
        }))

    except Exception as e:  # ADD ERROR HANDLING
      print(f"Error during streaming: {e}")
      self.is_connected = False
