from channels.generic.websocket import AsyncWebsocketConsumer
from .agents.chat_agent import ConversationAgent
import json
from app.models import User, Topic, Message, Chat_Session
from channels.db import database_sync_to_async
import asyncio
from api.agents.chat_graph import ChatGraph


class ChatConsumer(AsyncWebsocketConsumer):

  async def connect(self):
    # Get user_id from URL params
    self.user_id = self.scope['url_route']['kwargs']['user_id']
    self.model = self.scope['url_route']['kwargs']['model']
    print(f"Connecting with user_id: {self.user_id}, model: {self.model}")

    try:

      # Get user and topics
      self.user = await database_sync_to_async(User.objects.get
                                               )(id=self.user_id)
      self.topics = await database_sync_to_async(lambda: list(
          Topic.objects.filter(user_id=self.user_id, active=True)))()

      # Create Chat Session
      self.chat_session = await database_sync_to_async(
          Chat_Session.objects.create)(user=self.user)
      print(f"Chat session created for user: {self.user.username}")

      # Initialize agent
      self.agent = ConversationAgent(username=self.user.username,
                                     topics=self.topics,
                                     type=self.model)

      # Accept the connection
      await self.accept()
      print(f"Connection accepted for user: {self.user.username}")

      # Send initial connection message
      try:
        await self.send(text_data=json.dumps(
            {
                'type': 'connection_status',
                'status': 'connected',
                'message': f'Connected as {self.user.username}'
            }))
        print("Sent connection status message")

        # Send test ping
        await self.send(text_data=json.dumps({
            'type': 'ping',
            'message': 'ping'
        }))
        print("Sent ping message")

      except Exception as e:
        print(f"Error sending initial messages: {str(e)}")
        raise

    except User.DoesNotExist:
      print(f"User not found: {self.user_id}")
      await self.close()
    except Exception as e:
      print(f"Connection error: {str(e)}")
      await self.close()

    # self.user_id = self.scope['url_route']['kwargs']['user_id']
    # self.model = self.scope['url_route']['kwargs']['model']
    # print(f"Connecting with user_id: {self.user_id}, model: {self.model}")

    # try:
    #   self.agent = ChatGraph(username="ahoj",
    #                          topics=["topic1", "topic2", "topic3"])

    #   # Accept the connection first
    #   await self.accept()

    #   # Test the graph
    #   async for response in self.agent.generate_response("I am"):
    #     print("Response:", response)
    #     # Optionally send it through websocket
    #     await self.send(text_data=json.dumps({
    #         'type': 'message',
    #         'content': response
    #     }))

  async def disconnect(self, close_code):
    print(
        f"Disconnecting user {getattr(self, 'user_id', 'unknown')}, code: {close_code}"
    )
    # Cleanup if needed
    pass

  async def receive(self, text_data):
    """Handle incoming messages"""
    print(f"Received raw message: {text_data}")

    try:
      # Parse the incoming message
      data = json.loads(text_data)
      message_type = data.get('type', 'message')

      # Handle different message types
      if message_type == 'ping':
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'message': 'pong'
        }))
        return

      # Handle chat message
      query = data.get('query', '')
      if not query:
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': 'Empty query received'
        }))
        return

      print(f"Processing query: {query}")

      # Acknowledge receipt of message
      await self.send(text_data=json.dumps({
          'type': 'status',
          'message': 'Processing your message'
      }))

      # Stream the response
      try:

        # Add new message for user and this chat session
        await database_sync_to_async(Message.objects.create)(
            chat_session=self.chat_session,
            content=query,
            role='user',
        )

        assistant_message = ""
        async for token in self.agent.generate_response(query):
          if token:
            assistant_message += token
            message = {'type': 'token', 'token': token}
            print(f"Sending token: {token}")
            await self.send(text_data=json.dumps(message))
            await asyncio.sleep(0.01)  # Small delay between tokens

        # Finish streaming and send completion message
        print("Stream completed")
        await self.send(text_data=json.dumps({'type': 'stream_complete'}))

        # Save assistant message after stream completed

        await database_sync_to_async(Message.objects.create)(
            chat_session=self.chat_session,
            content=assistant_message,
            role='assistant',
        )
        print("Assistant message saved")

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

  async def send_error(self, message):
    """Utility method to send error messages"""
    try:
      await self.send(text_data=json.dumps({
          'type': 'error',
          'error': message
      }))
    except Exception as e:
      print(f"Error sending error message: {str(e)}")
