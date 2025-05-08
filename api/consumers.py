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

    # Get chat_session from URL params
    self.chat_session_id = self.scope['url_route']['kwargs'].get(
        'chat_session')
    print(f"Chat session ID from URL: {self.chat_session_id}")

    # Extract token from query string
    query_string = self.scope['query_string'].decode()
    print(f"Query string: {query_string}")

    from urllib.parse import parse_qs
    query_params = parse_qs(query_string)

    token = None
    if 'token' in query_params:
      token = query_params['token'][0]
      print(f"Found token in query params: {token[:10]}...")

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
        print(f"Other token error: {str(e)}")
        await self.close(code=4000)
        return
    else:
      print("No token found in query params")
      await self.close(code=4001)
      return

    # Now fetch the user and chat session
    try:
      from django.db import models
      from app.models import User, Chat_Session
      from channels.db import database_sync_to_async

      self.user = await database_sync_to_async(User.objects.get
                                               )(id=self.user_id)
      print(f"User found: {self.user.username}")

      self.chat_session = await database_sync_to_async(
          Chat_Session.objects.get)(id=self.chat_session_id, user=self.user)
      print(f"Chat session found")
    except User.DoesNotExist:
      print(f"User with ID {self.user_id} does not exist")
      await self.close(code=4002)
      return
    except Chat_Session.DoesNotExist:
      print(
          f"Chat session with ID {self.chat_session_id} not found for user {self.user_id}"
      )
      await self.close(code=4003)
      return
    except Exception as e:
      print(f"Unexpected error: {str(e)}")
      await self.close(code=4000)
      return

    # Accept the connection if everything is valid
    await self.accept()
    print("Connection accepted!")
    # GIVE AWAY

    # Fetch existing messages
    messages = await database_sync_to_async(lambda: list(
        Message.objects.filter(chat_session=self.chat_session).order_by(
            'date_created')))()

    # Convert messages to list of dicts
    message_data = [{
        'role': msg.role,
        'content': msg.content,
        'timestamp': msg.date_created.isoformat()
    } for msg in messages]

    # Send message history
    await self.send(text_data=json.dumps({
        'type': 'connection_status',
        'messages': message_data
    }))
    # GIVE AWAY

    # Create the agent after accepting connection
    print("Creating agent...")

    self.agent = await ConversationAgent.create(user=self.user,
                                                chat_session=self.chat_session,
                                                ws_consumer=self)

    async for token in self.agent.start_session():
      if token:  # Only send non-empty tokens
        await self.send(text_data=json.dumps({
            'type': 'message',
            'text': token
        }))

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
    self.is_monitoring = False
    if hasattr(self, 'monitor_task'):
      self.monitor_task.cancel()
      try:
        await self.monitor_task
      except asyncio.CancelledError:
        pass

    # await self.handle_close(complete=False)

  async def receive(self, text_data):

    # Rest of your existing receive code...
    try:
      data = json.loads(text_data)
      print(f"Received data: {data}")
      message_type = data.get('type', '')
      query = data.get('query', '')

      if not query:
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': 'Empty query received'
        }))
        return

      if message_type == 'user':
        # solve in conversation agent
        await database_sync_to_async(Message.objects.create)(
            chat_session=self.chat_session,
            content=query,
            role='user',
        )
        return

      if message_type == 'close':
        print("Received close message")
        await self.handle_close(complete=False)
        return

      if message_type == 'end':
        print("Received end message")
        await self.handle_close(complete=True)
        return

      # Acknowledge receipt of message
      await self.send(text_data=json.dumps({
          'type': 'status',
          'message': 'Processing your message'
      }))

      # Initialize agent_context as an empty dictionary
      agent_context = {}

      # If the message indicates a topic operation, add that information to the context
      if message_type == 'topic_operation':
        agent_context['topic_confirmation'] = data.get('topic_confirmation', 2)

      # Begin streaming the response from the agent

      try:
        assistant_message = ""  # Initialize an empty message to accumulate tokens

        # Get the response from the agent
        if self.agent is not None:
          response = await self.agent.run_agent(query, agent_context)
        else:
          response = None

        # Check if response is a ConversationState object
        if hasattr(response, 'response_type'):
          if response.response_type == "message":
            # Handle standard text response - split and stream tokens
            for token in response.response.split():
              token_with_space = token + " "
              assistant_message += token_with_space

              # fix in frontend
              await self.send(text_data=json.dumps({
                  'type': response.response_type,
                  'text': token_with_space
              }))
              await asyncio.sleep(0.01)
          elif response.response_type == "topic":
            # Handle special response types
            await self.send(text_data=json.dumps({
                'type': response.response_type,
                'text': response.response
            }))

        # Finish streaming and send completion message
        await self.send(text_data=json.dumps({'type': 'stream_complete'}))

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
      await self.send(text_data=json.dumps({'type': 'error', 'error': str(e)}))

  async def handle_close(self, complete: bool):
    """Handle closing operations including saving remaining time and sending final message if needed"""
    try:
      # Only try to save session state if agent exists
      if hasattr(self, 'agent') and self.agent is not None:
        # First save the session state (database operations only, no streaming)
        await self.agent.save_session_state(complete)

        # Then, if complete is True, get and stream the final message
        if complete:
          # Notice we're using agent.get_end_message() instead of end_session()
          # to just get the message without side effects
          final_message = await self.agent.get_end_message()

          if final_message:
            # Stream the message
            await self.stream_tokens(final_message)

      # Only close the connection if this was an explicit close request
      # AND after we've finished streaming any messages
      if not getattr(self, 'close_code', None):
        print("Closing WebSocket connection...")
        await self.close(code=4000)

    except Exception as e:
      print(f"Error during close: {str(e)}")
      try:
        await self.send(
            text_data=json.dumps({
                'type': 'error',
                'error': f"Error during close: {str(e)}"
            }))
      except:
        pass  # Connection might already be closed

  async def stream_tokens(self, message: str):
    """Helper method to stream tokens with proper format"""
    message = '*** ' + message
    # Split the message into tokens (words)
    tokens = message.split()

    # Iterate through tokens with their indices
    for i, token in enumerate(tokens):
      token_with_space = token
      if i != 0:  # Add space to all tokens except the first one
        token_with_space = " " + token

      await self.send(text_data=json.dumps({
          'type': 'message',
          'text': token_with_space
      }))
      await asyncio.sleep(0.01)  # Small delay

    # Send stream complete signal
    await self.send(text_data=json.dumps({'type': 'stream_complete'}))
