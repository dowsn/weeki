from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .graph_model import ConversationState
from .pinecone_manager import PineconeManager
from .actuality_engine import ActualityEngine
from .topic_manager import TopicCreator


class ConversationGraphManager:

  def __init__(self, agent):
    self.agent = agent
    self.pinecone = PineconeManager()
    self.actuality_engine = ActualityEngine()
    self.topic_creator = TopicCreator(agent.user_id)
    self.graph = self._create_conversation_graph()

  def _create_conversation_graph(self) -> StateGraph:
    """Create the conversation workflow graph"""
    workflow = StateGraph(ConversationState)

    # Add nodes for topic creation loop
    workflow.add_node("init_topic_creation", self._init_topic_creation)
    workflow.add_node("ask_topic_question", self._ask_topic_question)
    workflow.add_node("process_topic_response", self._process_topic_response)
    workflow.add_node("finalize_topic", self._finalize_topic)

    # Define topic creation loop
    def route_topic_creation(state: ConversationState) -> str:
        if state.topic_creation_complete:
            return "finalize_topic"
        if state.needs_user_confirmation:
            return "ask_topic_question"
        return "process_topic_response"

    # Add edges
    workflow.add_conditional_edges(
        "init_topic_creation",
        route_topic_creation
    )

    workflow.add_edge("ask_topic_question", "process_topic_response")
    workflow.add_conditional_edges(
        "process_topic_response",
        lambda x: "finalize_topic" if x.topic_creation_complete else "ask_topic_question"
    )

    # Add nodes
    workflow.add_node("check_conversation_start", self._check_start)
    workflow.add_node("cold_start", self._handle_cold_start)
    workflow.add_node("initialize_pinecone", self._initialize_from_pinecone)
    workflow.add_node("check_topic_shift", self._check_topic_shift)
    workflow.add_node("handle_topic_shift", self._handle_topic_shift)
    workflow.add_node("retrieve_context", self._retrieve_context)
    workflow.add_node("generate_response", self._generate_response)
    workflow.add_node("post_process", self._post_process)

    # Define routing functions
    async def route_start(state: ConversationState) -> str:
      if self._needs_cold_start(state):
        return "cold_start"
      if self._needs_initialization(state):
        return "initialize_pinecone"
      return "check_topic_shift"

    def route_topic_shift(state: ConversationState) -> str:
      return "handle_topic_shift" if self._has_topic_shift(
          state) else "retrieve_context"

    # Add conditional edges with routing functions
    workflow.add_conditional_edges("check_conversation_start", route_start)

    workflow.add_conditional_edges("check_topic_shift", route_topic_shift)

    # Add normal edges
    workflow.add_edge("cold_start", "generate_response")
    workflow.add_edge("initialize_pinecone", "check_topic_shift")
    workflow.add_edge("handle_topic_shift", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_response")
    workflow.add_edge("generate_response", "post_process")

    # Set entry/exit points
    workflow.set_entry_point("check_conversation_start")
    workflow.set_finish_point("post_process")

    return workflow

  # Node implementations
  async def _check_start(self, state: ConversationState) -> ConversationState:
    """Determine conversation start condition"""
    topic_count = await self.agent._get_topic_count()
    state.needs_new_topic = topic_count < 3
    return state

  async def _handle_cold_start(self,
                               state: ConversationState) -> ConversationState:
    """Handle new user with no existing topics"""
    topic_data = await self.agent._analyze_for_topic(state.current_input)
    if topic_data:
      state.topic_pool = [self.topic_creator.create_from_analysis(topic_data)]
      state.current_focus = state.topic_pool[0]
    return state

  async def _initialize_from_pinecone(
      self, state: ConversationState) -> ConversationState:
    """Initialize with existing Pinecone data"""
    topics = await self.pinecone.retrieve_topics(query=state.current_input,
                                                 user_id=self.agent.user_id)
    state.topic_pool = topics
    if topics:
      state.current_focus = topics[0]
    state.pinecone_initialized = True
    return state

  async def _check_topic_shift(self,
                               state: ConversationState) -> ConversationState:
    """Detect potential topic shifts"""
    if self.agent._detect_topic_shift(state.current_input,
                                      state.current_focus):
      state.topic_shift_detected = True
      retrieved = await self.pinecone.retrieve_topics(
          query=state.current_input, user_id=self.agent.user_id, min_score=0.7)
      state.retrieved_topics = retrieved
      state.needs_new_topic = not bool(retrieved)
    return state

  async def _handle_topic_shift(self,
                                state: ConversationState) -> ConversationState:
    """Process detected topic shift"""
    if state.needs_new_topic:
      topic_data = await self.agent._analyze_for_topic(state.current_input)
      if topic_data:
        new_topic = self.topic_creator.create_from_analysis(topic_data)
        state.topic_pool.append(new_topic)
        state.current_focus = new_topic
    else:
      new_focus = state.retrieved_topics[0]
      state.current_focus = new_focus
      state.topic_pool = self.actuality_engine.adjust_scores(
          state.topic_pool, new_focus)
    return state

  async def _retrieve_context(self,
                              state: ConversationState) -> ConversationState:
    """Get relevant context for response"""
    state.retrieved_logs = await self.pinecone.retrieve_logs(
        query=state.current_input,
        user_id=self.agent.user_id,
        topics=state.topic_pool)
    return state

  async def _generate_response(self,
                               state: ConversationState) -> ConversationState:
    """Generate response with context"""
    context = self.agent._build_context(state.retrieved_logs,
                                        state.topic_shift_detected)
    state.current_response = await self.agent._generate_base_response(
        state.current_input, context)
    return state

  async def _post_process(self, state: ConversationState) -> ConversationState:
    """Handle post-processing steps"""
    await self.agent.finalize_conversation()
    return state

  # Edge conditions
  def _needs_cold_start(self, state: ConversationState) -> bool:
    return not state.pinecone_initialized and state.needs_new_topic

  def _needs_initialization(self, state: ConversationState) -> bool:
    return not state.pinecone_initialized and not state.needs_new_topic

  def _is_initialized(self, state: ConversationState) -> bool:
    return state.pinecone_initialized

  def _has_topic_shift(self, state: ConversationState) -> bool:
    return state.topic_shift_detected

  def _no_topic_shift(self, state: ConversationState) -> bool:
    return not state.topic_shift_detected
