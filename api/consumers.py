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

    try:
      self.user = await database_sync_to_async(User.objects.get
                                               )(id=self.user_id)
      self.chat_session = await database_sync_to_async(
          Chat_Session.objects.get)(id=self.chat_session_id, user=self.user)
    except (User.DoesNotExist, Chat_Session.DoesNotExist) as e:
      raise ValueError(f"Invalid session: {str(e)}")

    try:
      self.agent = await ConversationAgent.create(
          user=self.user, 
          chat_session=self.chat_session, 
          ws_consumer=self
      )
    except ValueError as e:
      await self.close(code=4001)
      return

    # Accept the WebSocket connection
    await self.accept()

    # new code
    async for token in self.agent.start_session():
      await self.send(text_data=json.dumps({'type': 'token', 'token': token}))

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

      # Stream the response
      try:

        assistant_message = ""

        # the MAIN PART
        # async for token in self.agent.generate_response(query):
        async for token in self.agent.run_agent(query):
          if token:
            assistant_message += token
            message = {'type': 'token', 'token': token}
            print(f"Sending token: {token}")
            await self.send(text_data=json.dumps(message))
            await asyncio.sleep(0.01)  # Small delay between tokens

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
        
        await self.agent.save_session_state()

        # Only call close() if this was triggered by an explicit close request
        # rather than a disconnect
        if not self.close_code:
            await self.close(code=4000)

    except Exception as e:
        print(f"Close error: {str(e)}")
        await self.send_error(f"Close operation failed: {str(e)}")


  async def send_error(self, message):
    """Utility method to send error messages"""
    try:
      await self.send(text_data=json.dumps({
          'type': 'error',
          'error': message
      }))
    except Exception as e:
      print(f"Error sending error message: {str(e)}")
