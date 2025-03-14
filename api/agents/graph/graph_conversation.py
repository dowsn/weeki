from langgraph.graph import StateGraph
from api.agents.models.conversation_models import ConversationState, TopicState
from api.agents.handlers.topic_manager import TopicManager
from app.models import Topic
from langchain import hub
from datetime import datetime
from asgiref.sync import sync_to_async

import logging
import json
from typing import Any

# Initialize logging
logging.basicConfig(level=logging.INFO)


class ConversationGraphManager:

  def __init__(self, ai_model, topic_manager, log_manager):
    self.ai_model = ai_model
    self.graph = self._create_conversation_graph()
    self.topic_manager = topic_manager
    self.log_manager = log_manager
    self.char_threshold = 500
    self.message_char_threshold = 100

  def _create_conversation_graph(self) -> Any:
    workflow = StateGraph(ConversationState)

    # Basic conversation nodes
    workflow.add_node("start", self._handle_start)
    workflow.add_node("process_message", self._process_message)
    workflow.add_node("topic_exploration", self._topic_exploration_router)
    workflow.add_node("handle_end", self._handle_end)

    # Add edges with conditional routing
    workflow.add_conditional_edges("start", self._should_explore_topics, {
        True: "topic_exploration",
        False: "process_message"
    })

    # Add conditional routing from topic_exploration
    workflow.add_conditional_edges("topic_exploration",
                                   self._should_process_message, {
                                       True: "process_message",
                                       False: "handle_end"
                                   })

    # Add edges to end
    workflow.add_edge("process_message", "handle_end")

    workflow.set_entry_point("start")
    workflow.set_finish_point("handle_end")

    compiled = workflow.compile()
    print(f"Graph compiled: {type(compiled)}")
    return compiled

  async def _should_process_message(self, state: ConversationState) -> bool:
    """Determine if we should process the message or go directly to end"""
    # If this flag is set in _discuss_topic, go to end
    return state.potential_topic == ""

  async def _topic_exploration_router(
      self, state: ConversationState) -> ConversationState:

    # loading in the messages that the icon appears there and icon at the bottom disappears and it pulsates
    # frontend after message please

    state.response_type = "topic"

    topic_confirmation = state.topic_confirmation
    state.topic_confirmation = 2

    if topic_confirmation == 1:
      state = await self._save_topic(state)
    elif topic_confirmation == 0:
      state = await self._leave_topic(state)
    elif topic_confirmation == 2:
      state.prepare_prompt_topic()

    return state

  async def _discuss_topic(self,
                           state: ConversationState) -> ConversationState:

    print("discussing")
    # Generate question based on current context
    prompt = hub.pull("topic_discuss")
    prompt = prompt.format(
        potential_topic=state.potential_topic,
        asked_questions=state.prompt_asked_questions,
        query=state.prompt_query,
    )
    print(f"prompt: {prompt}")

    response = await self.run_until_json(prompt)

    #json topic, question
    topic_name = response["topic_name"]
    text = response["text"]
    question = response["question"]

    state.potential_topic = f"Topic Name: {topic_name}\n"
    state.potential_topic += f"Topic Description: {text}"

    first_sentence = "Ok, looks like we might have a new topic here we haven't discussed yet. Am I right?" if state.prompt_asked_questions == "NA" else "Let's explore this new topic further."

    response_text = first_sentence + " Here is how I understand it so far:\n\nTopic name: " + topic_name + "\nDescription: " + text + "\n\nMaybe this would also interest me:" + question + " " + "\n\nDo you want to explore this topic further? Do you want to save it? Or do you want to leave the exploration of the topic and go on with the conversation."

    # Set the response in a way that will be preserved
    state.response = response_text

    # Ensure the flag is set properly
    print(f"Response in _discuss_topic: {state.response[:50]}...")

    return state

  async def _leave_topic(self, state: ConversationState) -> ConversationState:
    state.potential_topic = ""
    state.prompt_asked_questions = ""

    print("leaving topic")
    # Fix: await the coroutine
    state = await self._process_message(state)

    return state

  async def run_until_json(self, prompt, max_attempts=3):
    for attempt in range(max_attempts):
      try:
        response_obj = self.ai_model.invoke(prompt)
        content = response_obj.content.strip()

        # Try to find JSON in the response
        if '{' in content and '}' in content:
          json_start = content.find('{')
          json_end = content.rfind('}') + 1
          json_str = content[json_start:json_end]
          parsed = json.loads(json_str)
          return parsed
        else:
          logging.warning(f"No JSON structure found in: {content[:100]}...")

      except json.JSONDecodeError as e:
        logging.warning(f"JSON decode error on attempt {attempt+1}: {str(e)}")
      except Exception as e:
        logging.error(f"Error during JSON extraction: {str(e)}")

      # Modify prompt to be clearer about JSON requirements
      prompt = f"Please respond with valid JSON only containing 'name' and 'text' fields. Original prompt: {prompt}"

    # If we reach here, we've failed after max_attempts
    logging.error(f"Failed to get valid JSON after {max_attempts} attempts")
    return {
        "name": "",
        "text": ""
    }  # Return empty defaults instead of raising exception

  async def _save_topic(self, state: ConversationState) -> ConversationState:
    """Validate if we hav
    e enough information about the topic"""
    # Analyze collected responses
    prompt = hub.pull("create_topic_json")
    prompt = prompt.format(topic=state.potential_topic)

    response = await self.run_until_json(prompt)

    print(f"response ii: {response}")

    topic_name = response.get('name', '')
    topic_text = response.get('text', '')

    # Validation
    if not topic_name or topic_name == "NA" or not topic_text:
      logging.warning(f"Missing expected fields in response: {response}")
      # Return to previous state or use default values
      return await self._leave_topic(state)  # Exit topic exploration

    #create embed first, how is confidence created at the beginning of chat session
    embedding = self.topic_manager.create_embedding(topic_text)

    potential_topic = Topic(name=topic_name,
                            description=topic_text,
                            active=True,
                            user_id=state.user_id)

    await sync_to_async(potential_topic.save)()

    topic_state = TopicState(
        topic_id=potential_topic.pk,
        topic_name=topic_name,
        text=topic_text,
        confidence=0.85,
        embedding=embedding,
    )

    state.cached_topics.append(topic_state)
    state.current_topics.append(topic_state)

    state = await self._leave_topic(state)

    return state

  async def _handle_start(self, state: ConversationState) -> ConversationState:
    """Start a new conversation"""
    if state.potential_topic == "":
      # Check logs and topics when either:
      # 1. There are no current logs or topics yet, OR
      # 2. We haven't checked for a while (based on character thresholds)
      if (len(state.current_logs) == 0 or len(state.current_topics) == 0) or (
          state.chars_since_check < self.char_threshold
          or len(state.current_message) < self.message_char_threshold):
        await state.update_embedding()
        state = await self.topic_manager.check_topics(state)
        state = await self.log_manager.check_logs(state)
        state.saved_query = state.prompt_query

    return state

  async def _should_explore_topics(self, state: ConversationState) -> bool:
    """Determine if we should explore topics based on state"""
    return state.potential_topic != ""

  async def _process_message(self, state: ConversationState):
    # here update
    print("process message")
    state.response_type = "message"

    state.prepare_prompt_process_message()

    first_sentence = ""
    if state.saved_query != "":
      state.prompt_query = state.saved_query
      state.saved_query = ""
      first_sentence = "Ok, let's continue with the conversation.\n"

    prompt = hub.pull("chat_mr_week")

    prompt = prompt.format(
        conversation_history=state.prompt_conversation_history,
        query=state.prompt_query,
        topics=state.prompt_topics,
        character=state.character,
        username=state.username,
        logs=state.prompt_logs)

    response_obj = self.ai_model.invoke(prompt)

    response = response_obj.content

    response = first_sentence + response

    state.response = response
    return state

  async def _handle_end(self, state: ConversationState) -> ConversationState:
    print(f"In _handle_end, state type: {type(state)}")
    print(f"State attributes: {dir(state)}")
    print(f"Has response: {hasattr(state, 'response')}")
    if hasattr(state, 'response'):
      print(f"Response value: {state.response[:50]}...")

    state.add_response(state.response)
    return state
