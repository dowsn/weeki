# moment_manager.py
import asyncio
from api.agents.handlers.conversation_helper import ConversationHelper
from api.agents.models.conversation_models import ConversationState, TopicState, MessageState
from app.models import Chat_Session, Message, Profile, Topic
from channels.db import database_sync_to_async
from api.agents.graph.graph_conversation import ConversationGraphManager
from api.agents.handlers.time_manager import TimeManager
from api.agents.handlers.topic_manager import TopicManager
from api.agents.handlers.log_manager import LogManager
from api.agents.handlers.session_manager import SessionManager
from api.agents.handlers.pinecone_manager import PineconeManager


class MomentManager:

  def __init__(self,
               user,
               chat_session,
               ai_model,
               stream_message,
               ws_consumer=None):
    self.user = user
    self.has_message = False
    self.chat_session = chat_session
    self.ai_model = ai_model
    self.remaining_minutes = getattr(self.chat_session, 'time_left')
    print(f"Remaining minutes: {self.remaining_minutes}")

    self.pending_time_events = []  # ADD THIS LINE
    self.session_ended = False  # ADD THIS LINE
    self.ws_consumer = ws_consumer  # ADD THIS LINE

    self.stream_message = stream_message
    self.converstation_helper = ConversationHelper(ai_model=self.ai_model)
    self.pinecone_manager = PineconeManager(user_id=self.user.id)
    self.topic_manager = TopicManager(self.pinecone_manager)
    self.log_manager = LogManager(self.pinecone_manager)

    self.state: ConversationState = self._initialize_state()
    self.time_manager: TimeManager = TimeManager(
        chat_session=self.chat_session,
        remaining_minutes=self.remaining_minutes,
        on_time_update=self._on_time_update)
    self.session_manager: SessionManager = SessionManager(
        self.chat_session, self.pinecone_manager, self.topic_manager,
        self.log_manager, self.ai_model, self.converstation_helper)

    self.session_manager.update_state(self.state)

    self.graph: ConversationGraphManager = self._setup_graph()

  def _initialize_state(self) -> ConversationState:

    return ConversationState(
        chat_session_id=self.chat_session.pk,
        user_id=int(self.user.id),
        username=str(self.user.username),
        prompt_asked_questions=self.chat_session.asked_questions or "",
        potential_topic=self.chat_session.potential_topic
        or "",  # Use empty string if None
        saved_query=self.chat_session.saved_query or "",
        topic_names=self.chat_session.topic_names
        or "")  # Use empty string if None)

  def get_current_state(self) -> ConversationState:
    return self.state

  def _setup_graph(self):
    return ConversationGraphManager(
        ai_model=self.ai_model,
        topic_manager=self.topic_manager,
        log_manager=self.log_manager,
        conversation_helper=self.converstation_helper).graph

  async def test_ai_model(self):
    """
    Test AI model during initialization to verify it's working correctly.
    This runs asynchronously after the MomentManager is created.
    """
    print("=== Testing AI Model during MomentManager initialization ===")

    try:
      # Check if AI model is properly initialized
      if self.ai_model is None:
        print("ERROR: AI model is None - not initialized")
        return False

      print(f"AI model type: {type(self.ai_model)}")

      # Test basic invocation
      print("Testing basic model invocation...")
      test_prompt = "Please respond with a simple 'Hello, testing!' to verify you're working."

      # Use the same configuration as in session_manager
      test_config = {
          "configurable": {
              "foo_temperature": 0.6,
              "foo_reasoning_effort": "low"
          }
      }

      # Invoke the model and capture any errors
      try:
        response = self.ai_model.invoke(test_prompt, config=test_config)
        print(f"Response type: {type(response)}")

        # Handle different response formats
        if hasattr(response, 'content'):
          response_content = response.content
          print(f"Response content attribute: {response_content}")
        elif isinstance(response, dict) and 'content' in response:
          response_content = response['content']
          print(f"Response content dict key: {response_content}")
        else:
          response_content = str(response)
          print(f"Raw response (converted to string): {response_content}")

        print("AI model test completed successfully during initialization")
        return True

      except Exception as invoke_error:
        print(
            f"ERROR during model invocation in init test: {type(invoke_error).__name__}: {str(invoke_error)}"
        )
        import traceback
        traceback.print_exc()
        return False

    except Exception as e:
      print(f"ERROR during overall init test: {type(e).__name__}: {str(e)}")
      import traceback
      traceback.print_exc()
      return False

  async def load_messages(self):
    """Load messages from the database and populate state.messages list"""

    @database_sync_to_async
    def get_first_message():
      return Message.objects.filter(
          chat_session=self.chat_session).order_by('date_created').first()

    @database_sync_to_async
    def get_messages():
      return list(
          Message.objects.filter(chat_session=self.chat_session,
                                 show_in=True).order_by('date_created'))

    db_messages = await get_messages()

    one_message = await get_first_message()

    self.has_message = one_message is not None

    # Remove the first message if any (system message

    # Clear existing messages
    self.state.messages = []

    # Convert database messages to state message format
    for msg in db_messages:
      role = 'Human' if msg.role == 'user' else 'Assistant'

      message = MessageState(role=role,
                             content=msg.content,
                             show_in=msg.show_in)

      self.state.messages.append(message)

  async def load_character(self):

    if self.chat_session.character:
      self.state.character = self.chat_session.character
    else:

      def get_profile():
        return Profile.objects.filter(user=self.user).first()

      profile = await database_sync_to_async(get_profile)()

      # fix
      self.state.character = profile.character

  async def _on_time_update(self, elapsed_minutes: int):
    """Handle time updates with proper session state management"""

    # Check if session is already ended or state is invalid
    if self.session_ended:
      print("Session already ended, ignoring time update")
      return

    if not self.state:
      print("State is None, stopping time monitoring")
      self.session_ended = True
      self.time_manager.stop_monitoring()
      return

    self.remaining_minutes -= elapsed_minutes

    print(
        f"Time update: {elapsed_minutes} elapsed, {self.remaining_minutes} remaining"
    )
    print(f"remaining_minutes {self.remaining_minutes}")

    # 5-minute warning (only once)
    if self.remaining_minutes == 5 and not hasattr(self, '_ending_soon_sent'):
      print("Time warning: 5 minutes remaining")
      self._ending_soon_sent = True
      try:
        # Check state before calling handle_ending_soon
        if self.state and hasattr(self.state, 'username'):
          message = await self.session_manager.handle_ending_soon()
          if message and not self.session_ended:
            await self.stream_message(message)
        else:
          print("Cannot send ending soon message - state or username is None")
      except Exception as e:
        print(f"Error in ending soon handler: {e}")

    # Session end (only once)
    elif self.remaining_minutes == 0 and not self.session_ended:
      print("Session time expired - triggering automatic end")
      self.session_ended = True
      print("DEBUG: Stopping time manager from moment_manager timeout")
      self.time_manager.stop_monitoring()

      # Instead of handling everything here, just notify the WebSocket
      if self.ws_consumer and self.ws_consumer.is_connected:
        print("DEBUG: Scheduling timeout handling in WebSocket context")
        # Schedule the timeout handling in the WebSocket's event loop
        asyncio.create_task(self.ws_consumer.handle_timeout())

  def is_session_ended(self):
    """Check if session ended due to time"""
    return self.session_ended

  async def run_agent(self, query: str,
                      agent_context: dict) -> ConversationState:

    self.state.add_context(agent_context)

    self.state.add_message(query)

    # Add logging before graph invocation

    # Run through the graph and get the updated state
    result = await self.graph.ainvoke(self.state)
    print(f"Graph execution completed, result type: {type(result)}")

    # Ensure we have a proper ConversationState object
    if isinstance(result, dict):
      print("Converting dict result to ConversationState")
      try:

        result = ConversationState(**dict(result))
      except Exception as e:
        print(f"Error converting result to ConversationState: {str(e)}")
        # If conversion fails, just use the dict directly
        pass

    # Update our state with the result
    self.state = result

    # Update the chat session with current state values
    await self._update_chat_session_state()

    if isinstance(self.state, ConversationState):
      return self.state
    else:
      raise TypeError("Unexpected state type. Expected 'ConversationState'.")

  async def _update_chat_session_state(self):
    """Update the chat session with current state values"""
    updates = {
        'potential_topic': getattr(self.state, 'potential_topic', ""),
        'saved_query': getattr(self.state, 'saved_query', ""),
        'character': getattr(self.state, 'character', ""),
        'topic_names': getattr(self.state, 'topic_names', ""),
        'topic_ids': getattr(self.state, 'topic_ids', ""),
        'asked_questions': getattr(self.state, 'prompt_asked_questions', "")
    }

    @database_sync_to_async
    def update_session():
      for field, value in updates.items():
        setattr(self.chat_session, field, value)
      self.chat_session.save(update_fields=list(updates.keys()))

    await update_session()


# initialize state and first message

  async def load_current_topics(self):
    topic_ids_str = self.chat_session.topic_ids
    if not topic_ids_str or not topic_ids_str.strip():
      # Handle empty case
      return

    try:
      topic_ids = [
          int(id_str) for id_str in topic_ids_str.split(',') if id_str.strip()
      ]

      if topic_ids:
        # Define a separate function for clarity
        @database_sync_to_async
        def get_topics():
          return list(Topic.objects.filter(id__in=topic_ids).values())

        # Call the wrapped function
        topics = await get_topics()

        for topic in topics:
          topic_state = TopicState(topic_id=topic['id'],
                                   topic_name=topic['name'],
                                   text=topic['description'],
                                   confidence=0.85)
          self.state.current_topics.append(topic_state)

        print("current_topics", self.state.current_topics)
    except (ValueError, AttributeError) as e:
      # Handle conversion errors
      print(f"Error loading topics: {e}")

  async def load_previous_session(
      self):  # Replace with your actual function name
    # Define a separate named function for clarity
    @database_sync_to_async
    def get_last_chat_session():
      return Chat_Session.objects.filter(user=self.user,
                                         time_left=0).order_by('-id').first()

    # Call the wrapped function
    last_chat_session = await get_last_chat_session()

    if last_chat_session:
      self.state.previous_summary = last_chat_session.summary

  async def start_session(self) -> str:
    await self.time_manager.start_monitoring()
    await self.load_messages()
    await self.load_character()
    await self.load_current_topics()
    await self.load_previous_session()

    print("messages_loaded", self.state.messages)

    if not self.has_message:
      self.session_manager.update_state(self.state)
      return await self.session_manager.handle_start()
    return ""

  async def get_remaining_time(self) -> int:
    remaining_time = await self.time_manager.get_remaining_time()
    return int(remaining_time)

  async def end_session(self):
    """REPLACE ENTIRE METHOD - Handle explicit session end"""
    # if self.session_ended:
    #   return ""  # Already ended

    self.session_ended = True
    print("DEBUG: Stopping time manager from end_session")
    self.time_manager.stop_monitoring()

    self.session_manager.update_state(self.state)

    # Run handle_state_end without timeout
    try:
      print("DEBUG: About to call handle_state_end")
      await self.session_manager.handle_state_end()
      print("DEBUG: handle_state_end completed successfully")
    except Exception as e:
      print(
          f"ERROR: handle_state_end failed: {e} - continuing with end message")

    print("DEBUG: About to call handle_end")
    response = await self.session_manager.handle_end()
    print(
        f"DEBUG: handle_end completed, response length: {len(response) if response else 0}"
    )
    return response.strip() if response else ""
