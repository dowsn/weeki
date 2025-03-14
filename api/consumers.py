from channels.generic.websocket import AsyncWebsocketConsumer
from .agents.main.conversation_agent import ConversationAgent
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
    # Get user_id from URL params
    self.user_id = self.scope['url_route']['kwargs']['user_id']
    self.chat_session_id = self.scope['url_route']['kwargs']['chat_session']
    self.agent = None

    try:
      self.user = await database_sync_to_async(User.objects.get
                                               )(id=self.user_id)
      self.chat_session = await database_sync_to_async(
          Chat_Session.objects.get)(id=self.chat_session_id, user=self.user)
    except (User.DoesNotExist, Chat_Session.DoesNotExist) as e:
      raise ValueError(f"Invalid session: {str(e)}")

    # Accept the WebSocket connection before creating agent
    await self.accept()

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
        'type': 'message_history',
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
            'type': 'token',
            'token': token
        }))

  async def disconnect(self, close_code):
    self.is_monitoring = False
    if hasattr(self, 'monitor_task'):
      self.monitor_task.cancel()
      try:
        await self.monitor_task
      except asyncio.CancelledError:
        pass

    await self.handle_close()

  async def receive(self, text_data):

    # Rest of your existing receive code...
    try:
      data = json.loads(text_data)
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

        await self.handle_close()
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
        agent_context['topic_operation'] = data.get('confirm', 2)

      # Begin streaming the response from the agent

      try:
        assistant_message = ""  # Initialize an empty message to accumulate tokens

        # Get the response from the agent
        response = await self.agent.run_agent(query, agent_context)

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

  async def handle_close(self):
    """Handle closing operations including saving remaining time"""
    try:
      # Only try to save session state if agent exists
      if hasattr(self, 'agent') and self.agent is not None:
        await self.agent.save_session_state()

      # Only call close() if this was triggered by an explicit close request
      # rather than a disconnect
      if not getattr(self, 'close_code', None):
        await self.close(code=4000)

    except Exception as e:
      print(f"Close error: {str(e)}")
    # Only try to send error if we still have a connection
    try:
      await self.send_error(f"Close operation failed: {str(e)}")
    except Exception:
      pass  # Connection might already be closed

  async def send_error(self, message):
    """Utility method to send error messages"""
    try:
      await self.send(text_data=json.dumps({
          'type': 'error',
          'error': message
      }))
    except Exception as e:
      print(f"Error sending error message: {str(e)}")
