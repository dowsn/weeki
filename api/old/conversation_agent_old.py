from typing import AsyncGenerator, Dict, List, Optional
from langchain_xai import ChatXAI
import logging
from langchain import hub

from .graph_model import ConversationState, SessionType
from .graph_manager import ConversationGraphManager
from .pinecone_manager import PineconeManager

logger = logging.getLogger(__name__)


class ConversationAgent:

  def __init__(self,
               username: str,
               user_id: int,
               chat_session_id: int,
               model: Optional[ChatXAI] = None,
               temperature: float = 0.8,
               window_size: int = 12,
               messages: List[Dict] = None):
    """Initialize conversation agent with LangGraph workflow"""
    self.username = username
    self.user_id = user_id
    self.chat_session_id = chat_session_id
    self.messages = messages or []

    # Initialize LLM
    self.model = model or ChatXAI(
        model="grok-2-1212", temperature=temperature, max_tokens=1000)

    # Initialize base state
    self.state = ConversationState(window_size=window_size)

    # Initialize graph workflow
    self.graph_manager = ConversationGraphManager(self)
    self.workflow = self.graph_manager.graph

    # Load base prompt
    self.prompt = hub.pull("chat_mr_week:02e4c2fd")

  async def process_message(self, query: str) -> AsyncGenerator[str, None]:
    """Process message through LangGraph workflow"""
    try:
      # Update state with new input
      self.state.current_input = query

      # Run the workflow
      final_state = await self.workflow.ainvoke(self.state)

      # Stream the response
      if final_state.error_occurred:
        yield f"I apologize, but I encountered an error: {final_state.error_message}"
        return

      if final_state.current_response:
        # Split response into tokens for streaming
        for token in final_state.current_response.split():
          yield token + " "
      else:
        yield "I apologize, but I wasn't able to generate a proper response."

    except Exception as e:
      logger.error(f"Error in process_message: {str(e)}")
      yield "I apologize, but I encountered an unexpected error."

  async def get_user_topic_count(self) -> int:
    """Get count of user's topics from database"""
    return await Topic.objects.filter(user_id=self.user_id,
                                      active=True).acount()

  def _update_conversation_context(self):
    """Update conversation context with windowed messages"""
    self.state.conversation_cache = window_messages(self.messages,
                                                    self.window_size)

  # async def process_message(self, query: str) -> AsyncGenerator[str, None]:
  #   """Main entry point for processing messages"""
  #   try:
  #     # Update conversation context
  #     self._update_conversation_context()

  #     if not self.state.pinecone_initialized:
  #       # Check if we need cold start (less than 3 topics)
  #       topic_count = await self.get_user_topic_count()

  #       if topic_count < 3:
  #         async for token in self._handle_cold_start(query):
  #           yield token
  #         return
  #       else:
  #         # Normal start - retrieve from Pinecone
  #         await self._initialize_from_pinecone(query)

  #     # Regular message processing
  #     async for token in self._handle_message(query):
  #       yield token

  #   except Exception as e:
  #     logger.error(f"Error in process_message: {str(e)}")
  #     yield "I apologize, but I encountered an error."

  async def _initialize_from_pinecone(self, query: str) -> None:
    """Initialize topic pool from Pinecone"""
    topics = await self.pinecone.retrieve_topics(query=query,
                                                 user_id=self.user_id,
                                                 top_k=5)
    self.state.topic_pool = topics
    self.state.pinecone_initialized = True

  async def _handle_message(self, query: str) -> AsyncGenerator[str, None]:
    """Handle regular message processing"""
    try:
      # Retrieve fresh context
      retrieved_topics = await self.pinecone.retrieve_topics(
          query=query, user_id=self.user_id, min_score=0.5)

      if retrieved_topics:
        self._update_pool_with_retrieved(retrieved_topics)

        if self._detect_topic_shift(query):
          # Try to find topic in Pinecone first
          new_topics = await self.pinecone.retrieve_topics(
              query=query, user_id=self.user_id, min_score=0.7)

          if new_topics:
            self._boost_topic(new_topics[0])
          else:
            # For now, just add potential topic without interaction
            # TODO: Implement proper interactive flow
            topic_data = await self._analyze_for_topic(query)
            if topic_data:
              new_topic = TopicState(**topic_data)
              self._add_topic_to_pool(new_topic)

      # Get fresh logs for context
      logs = await self.pinecone.retrieve_logs(query=query,
                                               user_id=self.user_id)

      # Generate response
      context = self._build_context(logs)
      prompt = self.prompt.partial(username=self.username,
                                   topics=str([{
                                       t.name: t.description
                                   } for t in context['topics']]),
                                   chat_memory=context['conversation'],
                                   query=query,
                                   user_context=str(context['logs']))

      async for token in self.model.astream(prompt):
        yield token

    except Exception as e:
      logger.error(f"Error handling message: {str(e)}")
      yield "I encountered an error processing your message."

  async def _analyze_for_topic(self, query: str) -> Optional[Dict]:
    """Analyze query for potential topic without interaction"""
    prompt = f"""Analyze this message for a potential self-development topic:
    {query}

    Respond in JSON format with:
    - name: Short topic name
    - description: Detailed description (max 500 chars)
    """

    try:
      response = await self.model.ainvoke(prompt)
      return response
    except Exception as e:
      logger.error(f"Error analyzing topic: {str(e)}")
      return None

  async def _get_user_confirmation(self, confirm_prompt: str) -> bool:
    """
    Instead of actual user confirmation, analyze query for topic relevance.
    In future, this could be made interactive with real user input.
    """
    try:
      # Using existing topic analysis
      topic_data = await self._analyze_for_topic(
          self.state.conversation_cache[-1])
      # If we can detect a clear topic, consider it confirmed
      return bool(topic_data and topic_data.get('name')
                  and topic_data.get('description'))
    except Exception as e:
      logger.error(f"Error getting confirmation: {str(e)}")
      return False

  async def _get_topic_name(self, query: str) -> str:
    """
    Extract topic name using the model.
    Uses existing topic analysis.
    """
    try:
      topic_data = await self._analyze_for_topic(query)
      return topic_data.get(
          'name', 'Untitled Topic') if topic_data else 'Untitled Topic'
    except Exception as e:
      logger.error(f"Error getting topic name: {str(e)}")
      return 'Untitled Topic'

  async def _get_topic_description(self, query: str) -> str:
    """
    Extract topic description using the model.
    Uses existing topic analysis.
    """
    try:
      topic_data = await self._analyze_for_topic(query)
      return topic_data.get('description', 'No description available'
                            ) if topic_data else 'No description available'
    except Exception as e:
      logger.error(f"Error getting topic description: {str(e)}")
      return 'No description available'

  def _detect_topic_shift(self, query: str) -> bool:
    """Detect substantial topic shift based on semantic similarity"""
    if not self.state.current_focus:
      return True

    # Use LangChain's similarity calculation
    similarity = self.pinecone.embeddings.similarity(
        query, self.state.current_focus.description)
    return similarity < 0.6

  async def _create_topic_interactively(self,
                                        query: str) -> Optional[TopicState]:
    """Interactive topic creation flow"""
    confirm_prompt = (
        "I notice we're exploring something new. "
        "Would you like to make this a focus area for our discussions?")
    confirmation = await self._get_user_confirmation(confirm_prompt)

    if not confirmation:
      return None

    name = await self._get_topic_name(query)
    description = await self._get_topic_description(query)

    return TopicState(name=name, description=description, actuality=1.0)

  async def _handle_cold_start(self, query: str) -> AsyncGenerator[str, None]:
    """Handle cold start when user has fewer than 3 topics"""
    potential_topic = await self._detect_implicit_topic(query)

    if potential_topic:
      refined_topic = await self._refine_topic_with_user(potential_topic)
      if refined_topic:
        self.state.topic_pool.append(refined_topic)

        response = self._generate_cold_start_response(refined_topic)
        for token in response.split():
          yield token + " "

  async def _detect_implicit_topic(self, query: str) -> Optional[Dict]:
    """
    Detect potential topic from user's message.
    Uses _analyze_for_topic as it serves the same purpose.
    """
    return await self._analyze_for_topic(query)

  async def _refine_topic_with_user(self,
                                    topic_data: Dict) -> Optional[TopicState]:
    """
    For now, directly convert analyzed topic data to TopicState.
    In future, this could be interactive.
    """
    try:
      if not topic_data:
        return None

      return TopicState(name=topic_data.get('name', ''),
                        description=topic_data.get('description', ''),
                        actuality=1.0)
    except Exception as e:
      logger.error(f"Error refining topic: {str(e)}")
      return None

  def _generate_cold_start_response(self, topic: TopicState) -> str:
    """Generate response for newly created topic during cold start"""
    return (
        f"I see you're interested in {topic.name}. "
        f"I'll keep this as one of our focus areas. "
        "Feel free to tell me more about what you'd like to explore in this area."
    )

  async def _generate_topic_log(self, topic: TopicState) -> str:
    """
    Generate log entry summarizing discussion about a topic.
    Uses model to analyze conversation in context of the topic.
    """
    try:
      prompt = f"""Summarize the discussion about {topic.name}.
        Context: {self.state.conversation_cache}

        Generate a concise summary focusing on key points and insights.
        Keep under 500 characters.
        """

      summary = await self.model.ainvoke(prompt)
      return summary[:500]  # Ensure length limit

    except Exception as e:
      logger.error(f"Error generating topic log: {str(e)}")
      return f"Discussion about {topic.name}"

  def _update_pool_with_retrieved(self,
                                  retrieved_topics: List[TopicState]) -> None:
    """Update pool with retrieved topics"""
    current_ids = [t.id for t in self.state.topic_pool]

    for topic in retrieved_topics:
      if topic.id not in current_ids:
        topic.actuality = 0.5  # Start with medium actuality
        self.state.topic_pool.append(topic)

  def _boost_topic(self, topic: TopicState) -> None:
    """Boost topic actuality and update pool"""
    self.state.current_focus = topic
    self.state.topic_pool = self.actuality_engine.adjust_scores(
        self.state.topic_pool, topic)

  def _add_topic_to_pool(self, topic: TopicState) -> None:
    """Add new topic to pool and make it current focus"""
    self.state.topic_pool.append(topic)
    self._boost_topic(topic)

  def _build_context(self, logs: List[str]) -> Dict:
    """Build context for response generation"""
    return {
        'topics': self.state.topic_pool,
        'logs': logs,
        'conversation': self.state.conversation_cache
    }

  async def _generate_base_response(self, query: str, context: Dict) -> str:
    """Generate base response"""
    prompt = self.prompt.partial(username=self.username,
                                 topics=str([{
                                     t.name: t.description
                                 } for t in context['topics']]),
                                 chat_memory=context['conversation'],
                                 query=query,
                                 user_context=str(context['logs']))

    response = await self.model.ainvoke(prompt)
    return response

  def _apply_personality_layer(self, response: str) -> str:
    """Apply personality enhancements to response"""
    # Implement personality enhancement logic
    return response

  async def finalize_conversation(self) -> None:
    """Post-process conversation and update Pinecone"""
    # Generate logs for active topics
    for topic in self.state.topic_pool:
      log_text = await self._generate_topic_log(topic)
      await self.pinecone.upsert_log(log_text=log_text,
                                     user_id=self.user_id,
                                     topic_id=topic.id,
                                     chat_session_id=self.chat_session_id)

    # Update topics in Pinecone
    await self.pinecone.upsert_topics(topics=self.state.topic_pool,
                                      user_id=self.user_id)
