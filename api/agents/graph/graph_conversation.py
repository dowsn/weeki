from langgraph.graph import StateGraph
from api.agents.models.conversation_models import ConversationState, TopicState, TopicJSON, TopicPotentialJSON
from api.agents.handlers.topic_manager import TopicManager
from app.models import Prompt, Topic
from langchain import hub
from datetime import datetime
from asgiref.sync import sync_to_async
from api.agents.handlers.conversation_helper import ConversationHelper

import logging
import json
from typing import Any
from langsmith import Client

# Initialize logging
logging.basicConfig(level=logging.INFO)


class ConversationGraphManager:

  def __init__(self, ai_model, topic_manager, log_manager,
               conversation_helper):
    self.ai_model = ai_model
    self.graph = self._create_conversation_graph()
    self.topic_manager = topic_manager
    self.log_manager = log_manager
    self.conversation_helper = conversation_helper

    self.client = Client()

  def _create_conversation_graph(self) -> Any:
    workflow = StateGraph(ConversationState)

    # Basic conversation nodes
    workflow.add_node("start", self._handle_start)
    workflow.add_node("process_message", self._process_message)
    workflow.add_node("validation", self._validation)
    workflow.add_node("discuss_topic", self._discuss_topic)
    workflow.add_node("topic_exploration", self._topic_exploration_router)
    workflow.add_node("handle_end", self._handle_end)

    # Add edges with conditional routing
    workflow.add_conditional_edges("start", self._should_explore_topics, {
        True: "topic_exploration",
        False: "process_message"
    })

    # Add conditional routing from topic_exploration
    workflow.add_conditional_edges("topic_exploration",
                                   self._should_discuss_topic, {
                                       True: "discuss_topic",
                                       False: "handle_end"
                                   })

    # Add edges to end
    workflow.add_edge("process_message", "validation")
    workflow.add_edge("validation", "handle_end")

    workflow.set_entry_point("start")
    workflow.set_finish_point("handle_end")

    compiled = workflow.compile()
    return compiled

  async def _should_discuss_topic(self, state: ConversationState) -> bool:
    """Determine if we should process the message or go directly to end"""
    # If this flag is set in _discuss_topic, go to end
    return state.potential_topic != ""

  async def _topic_exploration_router(
      self, state: ConversationState) -> ConversationState:

    # loading in the messages that the icon appears there and icon at the bottom disappears and it pulsates
    # frontend after message please

    state.response_type = "topic"

    topic_confirmation = state.topic_confirmation

    if topic_confirmation == 1:
      state = await self._save_topic(state)
    elif topic_confirmation == 0:
      state = await self._leave_topic(state)
    elif topic_confirmation == 2:
      state.prompt_query = state.current_message

    return state

  async def _validation(self, state: ConversationState) -> ConversationState:
    # logic with checker of the response

    # Check if the response is valid
    if state.response == "":
      state.response = "Sorry, I didn't understand that. Can you please rephrase?"
    return state

  async def _discuss_topic(self,
                           state: ConversationState) -> ConversationState:

    print("discussing")
    # Generate question based on current context

    prompt = self.client.pull_prompt("topic_discuss")

    print("prompt_query_discuss, should be saved if saved query",
          state.prompt_query)

    prompt = prompt.invoke({
        "potential_topic": state.potential_topic,
        "asked_questions": state.prompt_asked_questions,
        "query": state.current_message
    })

    response = await self.conversation_helper.run_until_json(
        prompt=prompt, response_type=TopicPotentialJSON)

    #json topic, question
    topic_name = response["topic_name"]
    text = response["text"]
    question = response["question"]

    state.potential_topic = f"Topic Name: {topic_name}\n"
    state.potential_topic += f"Topic Description: {text}"

    state.prompt_asked_questions += f"{question}\n"

    first_sentence = "Ok, looks like we might have a new topic here we haven't discussed yet. Am I right?" if state.prompt_asked_questions == "" else "Let's explore this new topic further."

    response_text = first_sentence + " Here is how I understand it so far:\n\n" + topic_name + "\n\n" + text + "\n\nMaybe this would also interest me: " + question + " " + "\n\nDo you want to explore this topic further? Do you want to save it? Or do you want to leave the exploration of the topic and go on with the conversation."

    state.topic_names = response["topic_name"]

    # Set the response in a way that will be preserved
    state.response = response_text

    # Ensure the flag is set properly

    return state

  async def _leave_topic(self, state: ConversationState) -> ConversationState:
    state.prompt_asked_questions = ""

    # Process message with restored query and history
    state = await self._process_message(state)
    return state

  async def _save_topic(self, state: ConversationState) -> ConversationState:
    """Validate if we hav
    e enough information about the topic"""
    # Analyze collected responses

    #here

    prompt = self.client.pull_prompt("create_topic_json")

    prompt = prompt.invoke({
        "topic": state.potential_topic,
    })

    response = await self.conversation_helper.run_until_json(prompt, TopicJSON)

    topic_name = response.get('name', '')
    topic_text = response.get('text', '')

    # Validation
    if not topic_name or topic_name == "NA" or not topic_text:
      logging.warning(f"Missing expected fields in response: {response}")
      # Return to previous state or use default values
      return await self._leave_topic(state)  # Exit topic exploration

    #create embed first, how is confidence created at the beginning of chat session

    # Create topic in database
    potential_topic = TopicState(
        topic_id=0,
        topic_name=topic_name,
        text=topic_text,
        confidence=0.85,
        embedding=None,
    )

    # Create and store embedding in one step
    new_topic = await self.topic_manager.store_topic(topic=potential_topic,
                                                     state=state)

    state.current_topics.append(new_topic)

    state = await self._leave_topic(state)

    return state

  async def _handle_start(self, state: ConversationState) -> ConversationState:
    """Start a new conversation"""

    if state.potential_topic == "":

      state.split_messages(window_size=2000)

      same_topic = 0

      if len(state.current_topics) > 0:

        state.prepare_topics_to_prompt()

        prompt = self.client.pull_prompt("change_of_topics")

        change_of_topics_response = prompt.invoke({
            "conversation_history":
            state.prompt_conversation_history,
            "query":
            state.prompt_query,
            "topics":
            state.prompt_topics
        })

        response_obj = self.ai_model.invoke(change_of_topics_response)

        response = response_obj.content

        # 0 off topic
        if str(response) == "1":
          same_topic = 1

      if same_topic == 0:

        # Save query before potentially entering topic exploration
        # This will save the recent human messages up to 1000 chars
        print("🔧 DEBUG: About to create embedding...")
        await state.update_embedding()
        print(f"🔧 DEBUG: Embedding created! Length: {len(state.embedding) if state.embedding else 'None'}")
        print(f"🔧 DEBUG: Embedding type: {type(state.embedding)}")

        state.saved_query = state.prompt_query  # Save this for topic exploration

        print("🔧 DEBUG: About to call check_topics...")
        state = await self.topic_manager.check_topics(state)
        print("🔧 DEBUG: Returned from check_topics")

        print(f"potential_topic after check_topics: '{state.potential_topic}'")

    else:
      # Already in topic exploration, don't update saved_query
      pass

    return state

  async def _should_explore_topics(self, state: ConversationState) -> bool:
    """Determine if we should explore topics based on state"""
    should_explore = state.potential_topic != ""

    print("shold explore", should_explore)
    return should_explore

  async def _process_message(self, state: ConversationState):
    # here update
    state.response_type = "message"

    if not state.embedding:
      await state.update_embedding()

    state.embedding = None

    state = await self.log_manager.check_logs(state)

    state.prepare_prompt_process_message()

    state.saved_query = ""

    prompt = self.client.pull_prompt("chat_mr_week")

    # if leave topic
    end_sentence = ""
    if state.topic_confirmation == 0:
      end_sentence = "\n\nCould you please let me know if we talk about some topic we discussed already or is this a new topic? And if then tell please more about it."

    state.topic_confirmation = 2

    prompt = prompt.invoke({
        "username": state.username,
        "conversation_history": state.prompt_conversation_history,
        "query": state.prompt_query,
        "topics": state.prompt_topics,
        "character": state.prompt_character,
        "logs": state.prompt_logs,
    })


    state.potential_topic = ""

    response_obj = self.ai_model.invoke(prompt)

    response = response_obj.content

    response = response + end_sentence

    state.response = response
    return state

  async def _handle_end(self, state: ConversationState) -> ConversationState:

    # state.embedding = None

    state.current_logs = []

    if not state.saved_query:
      state.topic_names = ", ".join(topic.topic_name
                                    for topic in state.current_topics)
    print('topic names', state.topic_names)

    state.topic_ids = ", ".join(
        str(topic.topic_id) for topic in state.current_topics)

    if hasattr(state, 'response'):
      print(f"Response value: {state.response[:50]}...")

    state.add_response(state.response)
    return state
