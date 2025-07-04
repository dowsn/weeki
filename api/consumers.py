from channels.generic.websocket import AsyncWebsocketConsumer
from api.agents.main.conversation_agent import ConversationAgent
import json
from app.models import User, Topic, Message, Chat_Session
from channels.db import database_sync_to_async
import asyncio




class ChatConsumer(AsyncWebsocketConsumer):

  async def connect(self):

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
      await self.close(code=4003)
      return
    except Exception as e:
      print(f"Unexpected error: {str(e)}")
      await self.close(code=4000)
      return

    # Accept the connection if everything is valid
    await self.accept()
    self.is_connected = True

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


  async def disconnect(self, close_code):
    print(f"Disconnecting with code: {close_code}")
    self.is_connected = False

    # CRITICAL: Stop time monitoring FIRST
    if hasattr(self, 'agent') and self.agent is not None:
      if hasattr(self.agent,
                 'moment_manager') and self.agent.moment_manager is not None:
        if hasattr(self.agent.moment_manager, 'time_manager'):
          print("Stopping time manager from disconnect")
          self.agent.moment_manager.time_manager.stop_monitoring()
          # Also set session as ended to prevent further time updates
          self.agent.moment_manager.session_ended = True

    # Fix the order of monitoring cleanup
    if hasattr(self, 'is_monitoring'):
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
    # Early exit if connection is already closed
    if not self.is_connected:
      print("Ignoring message - connection already closed")
      return

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
            # Check if connection is still open before sending
            if self.is_connected:
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
            # Check if connection is still open before sending
            if self.is_connected:
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
                topics = response.topic_names if hasattr(response, 'topic_names') and response.topic_names else "No current topics"
                await self.stream_tokens(message=response.response,
                                         topics=topics,
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
      await self.send(text_data=json.dumps({'type': 'error', 'error': str(e)}))

  async def handle_timeout(self):
    """Handle automatic timeout - runs in WebSocket context, not monitoring task"""
    print("Handling automatic timeout in WebSocket context")

    # This now runs outside the monitoring task, so no cancellation issues
    await self.handle_close(complete=True)

  async def handle_close(self, complete: bool, message=""):
    """Simplified close handling with proper time manager cleanup"""

    if hasattr(self, '_closing') and self._closing:
      print("Already closing, ignoring duplicate close call")
      return

    self._closing = True
    print(
        f"handle_close called - complete: {complete}, has_message: {bool(message)}"
    )

    # Send processing status to frontend immediately
    if complete:
      await self.send(text_data=json.dumps({
          'type': 'processing_end',
          'text': '',
          'topics': ''
      }))

    final_message = message

    try:
      if hasattr(self, 'agent') and self.agent is not None:
        print(f"DEBUG: Agent exists, proceeding with close operations")

        # CRITICAL: Stop time monitoring IMMEDIATELY
        if hasattr(self.agent,
                   'moment_manager') and self.agent.moment_manager is not None:
          print("Stopping time manager from handle_close")
          self.agent.moment_manager.session_ended = True
          if hasattr(self.agent.moment_manager, 'time_manager'):
            self.agent.moment_manager.time_manager.stop_monitoring()

        # Save session state - skip for automatic timeout to prioritize final message
        if not complete:
          print(f"DEBUG: About to save session state with complete={complete}")
          try:
            await self.agent.save_session_state(complete)
            print(f"DEBUG: Session state saved successfully")
          except Exception as e:
            print(f"ERROR: Failed to save session state: {e}")
        else:
          print(f"DEBUG: Skipping save_session_state for automatic timeout - prioritizing final message")

        # Only get end message if we don't already have one and we're completing
        print(f"DEBUG: Checking end message conditions - complete={complete}, final_message={bool(final_message)}")
        if complete and not final_message:
          print("Getting final message from agent")

          try:
            final_message = await self.agent.end_session()
            print(
                f"Got end message from agent: {final_message[:100] if final_message else 'None'}..."
            )
          except Exception as e:
            print(f"ERROR: Failed to get end message from agent: {e}")
            final_message = "Session ended due to timeout."

        # Stream the final message if we have one
        if final_message and self.is_connected:
          print("Streaming final message")
          await self.stream_tokens(
              final_message,
              message_type="automatic_message",
              skip_new_message=True
          )  # Skip new_message since we already sent processing_end

        # Now save session state AFTER sending the final message (only for automatic timeout)
        if complete:
          print(f"DEBUG: Now saving session state after final message sent")
          try:
            await self.agent.save_session_state(complete)
            print(f"DEBUG: Session state saved successfully after final message")
          except Exception as e:
            print(f"ERROR: Failed to save session state after final message: {e}")

      # Close the connection
      if self.is_connected and not getattr(self, 'close_code', None):
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
                          message_type: str = "message",
                          skip_new_message: bool = False):
    """Helper method to stream tokens with proper format"""

    # ADD THIS CHECK - Check if connection is still active
    if not self.is_connected:
      print("Connection closed, stopping stream")
      return

    try:

      if message_type == "automatic_message" and not skip_new_message:
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
