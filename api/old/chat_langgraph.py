# from typing import TypedDict, Sequence, AsyncGenerator, List, Dict, Any, Annotated
# from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
# from langgraph.graph import StateGraph, END  # This is the correct import for LangGraph
# from langchain_core.tools import BaseTool
# from operator import itemgetter
# from langchain import hub
# from langchain_xai import ChatXAI
# from langchain_aws import ChatBedrockConverse
# import os

# class AgentState(TypedDict):
#   messages: Sequence[BaseMessage]
#   next: str

# class ConversationAgent:

#   def __init__(self,
#                username: str,
#                topics: list,
#                type: str = "xai",
#                model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
#                temperature: float = 0.8):
#     self.username = username
#     self.topics = self.process_topics(topics)
#     self.type = type
#     self.llm = self._initialize_llm(type, model, temperature)
#     self.prompt = self._initialize_prompt()
#     self.workflow = self._create_graph()
#     self.chain = self.workflow.compile()
#     self.memory_buffer: List[BaseMessage] = []

#   def _initialize_llm(self, type: str, model: str, temperature: float):
#     if type == 'xai':
#       return ChatXAI(
#           model="grok-2-1212",
#           temperature=temperature,
#           max_tokens=200,
#       )
#     return ChatBedrockConverse(
#         model=model,
#         temperature=temperature,
#         aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
#         aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
#         region_name="us-west-2",
#         max_tokens=200)

#   def _initialize_prompt(self):
#     prompt = hub.pull("chat_mr_week:02e4c2fd")
#     return prompt.partial(username=self.username, topics=self.topics)

#   @staticmethod
#   def process_topics(topics: list) -> str:
#     return ", ".join(topics)

#   async def process_message(self, state: AgentState) -> Dict:
#     messages = state["messages"]
#     if not messages:
#       return {"messages": messages, "next": END}

#     last_message = messages[-1]

#     if isinstance(last_message, HumanMessage):
#       try:
#         # Add the message to our memory buffer
#         self.memory_buffer.append(last_message)

#         # Prepare the input for the LLM
#         chain_input = {
#             "chat_memory": self.memory_buffer,
#             "query": last_message.content,
#             "topics": self.topics,
#             "user_context": "none",
#             "literature_help": "none"
#         }

#         response = await self.llm.ainvoke(chain_input)
#         ai_message = AIMessage(content=response)
#         self.memory_buffer.append(ai_message)

#         return {
#             "messages": [*messages, ai_message],
#             "next": "process"  # Continue processing
#         }
#       except Exception as e:
#         error_message = AIMessage(content=f"Error: {str(e)}")
#         return {"messages": [*messages, error_message], "next": END}

#     # If we reach here, check if we should end
#     if self.should_end(messages[-1].content):
#       return {"messages": messages, "next": END}
#     return {"messages": messages, "next": "process"}

#   def should_end(self, message: str) -> bool:
#     return any(phrase in message.lower()
#                for phrase in ["goodbye", "end conversation", "finish"])

#   def _create_graph(self) -> StateGraph:
#     workflow = StateGraph(AgentState)

#     # Add the processing node
#     workflow.add_node("process", self.process_message)

#     # Set the entry point
#     workflow.set_entry_point("process")

#     # Add edges based on "next" key in state
#     workflow.add_edge("process", END)
#     workflow.add_edge("process", "process")

#     return workflow

#   async def generate_response(self, query: str) -> AsyncGenerator[str, None]:
#     initial_state = {
#         "messages": [HumanMessage(content=query)],
#         "next": "process"
#     }

#     try:
#       result = await self.chain.ainvoke(initial_state)
#       for message in result["messages"]:
#         if isinstance(message, AIMessage):
#           yield message.content
#     except Exception as e:
#       yield f"Error: {str(e)}"

#   def get_conversation_history(self) -> list:
#     return self.memory_buffer

#   def clear_memory(self):
#     self.memory_buffer = []

# # Example of adding tools
# def add_tool_node(agent: ConversationAgent, tool: BaseTool):

#   async def execute_tool(state: AgentState) -> Dict:
#     messages = state["messages"]
#     last_message = messages[-1]

#     if isinstance(last_message, HumanMessage):
#       try:
#         result = await tool.ainvoke(last_message.content)
#         return {
#             "messages": [*messages, AIMessage(content=result)],
#             "next": "process"
#         }
#       except Exception as e:
#         return {
#             "messages":
#             [*messages, AIMessage(content=f"Tool error: {str(e)}")],
#             "next": END
#         }
#     return {"messages": messages, "next": "process"}

#   # Add tool node to graph
#   agent.workflow.add_node(f"tool_{tool.name}", execute_tool)

#   # Add routing logic
#   def route_to_tool(state: AgentState) -> bool:
#     if not state["messages"]:
#       return False
#     last_message = state["messages"][-1].content
#     return tool.name in last_message.lower()

#   # Update the graph structure
#   agent.workflow.add_conditional_edges("process", route_to_tool, {
#       True: f"tool_{tool.name}",
#       False: "process"
#   })

#   # Recompile the chain
#   agent.chain = agent.workflow.compile()
