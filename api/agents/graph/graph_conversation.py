from langgraph.graph import StateGraph
from api.agents.models.conversation_models import ConversationState
from api.agents.handlers.topic_manager import TopicManager
from langchain import hub


class ConversationGraphManager:

  def __init__(self, ai_model, topic_manager, log_manager):
    self.ai_model = ai_model
    self.graph = self._create_conversation_graph()
    self.topic_manager = topic_manager
    self.log_manager = log_manager

  def _create_conversation_graph(self) -> StateGraph:
    workflow = StateGraph(ConversationState)

    # Basic conversation nodes
    workflow.add_node("start", self._handle_start)

    workflow.add_node("topic_exploration", self._handle_topic_exploration)
    workflow.add_node("process_message", self._process_message)

    workflow.add_node("handle_end", self._handle_end)

    workflow.add_conditional_edges("start",
                                   self._explore_topics_or_process_message)

    workflow.set_entry_point("start")
    workflow.set_finish_point("handle_end")

    return workflow

  async def _handle_start(self, state: ConversationState) -> ConversationState:
    """Start a new conversation"""
    # create embed
    await state.update_embedding()

    if state.potential_topic is not None:
      state = self.topic_manager.check_topics(state)

    state = self.log_manager.check_logs(state)

    # clear embedding after being used
    state.embedding = None

    return state
    # load the last context in state

  async def _explore_topics_or_process_message(
      self, state: ConversationState) -> str:
    return "topic_exploration" if state.potential_topic is not None else "process_message"

  async def _process_message(self, state: ConversationState):

    prompt = hub.pull("chat_mr_week:02e4c2fd")

    prompt = prompt.format(messages=state.get_windowed_messages(),
                           topics=state.current_topics,
                           character=state.character,
                           username=state.username,
                           logs=state.current_logs)

    response = await self.ai_model.ainvoke(prompt)

    state.add_response(response)
    return state

  async def _handle_end(self, state: ConversationState):
    # Add ending logic here
    state.add_response("Conversation ended")
    return state

  async def _handle_topic_exploration(self, state: ConversationState):

    state.chars_since_check = 0

    state.potential_topic = TopicState(
        name="unknown",
        description="unknown",
        confidence=0.0,
        user_id=state.user_id,
        date_updated=datetime.now(),
    )


# from langgraph.graph import StateGraph
# from models.conversation_state import ConversationState
# from handlers.session_handlers import SessionHandlers
# from handlers.topic_handlers import TopicHandlers
# from handlers.engagement_handlers import EngagementHandlers

# class ConversationGraphManager:
#     def __init__(self, session_handlers: SessionHandlers,
#                  topic_handlers: TopicHandlers,

#                  # engagement_handlers: EngagementHandlers
#                 ):
#         self.session_handlers = session_handlers
#         self.topic_handlers = topic_handlers
#         # self.engagement_handlers = engagement_handlers
#         self.graph = self._create_conversation_graph()

#     def _create_conversation_graph(self) -> StateGraph:
#         workflow = StateGraph(ConversationState)

#         # Add nodes with handlers
#         workflow.add_node("check_time_status", self.session_handlers.check_time_status)
#         workflow.add_node("handle_ending_soon", self.session_handlers.handle_ending_soon)
#         workflow.add_node("handle_session_end", self.session_handlers.handle_session_end)
#         workflow.add_node("check_engagement", self.engagement_handlers.check_engagement)
#         workflow.add_node("process_topics", self.topic_handlers.process_topics)

#         # Add conditional edges
#         workflow.add_conditional_edges(
#             "check_time_status",
#             self.session_handlers.route_by_session_type
#         )

#         # Define standard edges
#         workflow.add_edge("handle_ending_soon", "process_topics")
#         workflow.add_edge("process_topics", "check_engagement")

#         workflow.set_entry_point("check_time_status")
#         workflow.set_finish_point("check_engagement")

#         return workflow
