from typing import Dict, Any, List
from langchain_xai import ChatXAI
from langchain import hub
from pydantic import BaseModel
from api.agents.handlers.conversation_helper import ConversationHelper

from api.agents.handlers.log_manager import LogManager
from api.agents.handlers.pinecone_manager import PineconeManager
from api.agents.handlers.topic_manager import TopicManager
from api.agents.models.conversation_models import ConversationState, LogJSON, TopicAndCharacterJSON, TopicState, LogState
from app.models import Topic, Log, Profile, Chat_Session, SessionLog, SessionTopic
from typing import Optional
from datetime import datetime
import json
from channels.db import database_sync_to_async
from langsmith import Client
import asyncio


class SessionManager:

  def __init__(self, chat_session: Chat_Session,
               pinecone_manager: PineconeManager, topic_manager: TopicManager,
               log_manager: LogManager, ai_model,
               conversation_helper: ConversationHelper):
    self.ai_model = ai_model
    self.chat_session = chat_session
    self.pinecone_manager = pinecone_manager
    self.topic_manager = topic_manager
    self.log_manager = log_manager
    self.session_ended = False  # ADD THIS LINE
    self.ending_soon_sent = False

    self.model_config_time = {
        "configurable": {
            "foo_temperature": 0.6,
            "foo_reasoning_effort": "low"
        }
    }

    self.client = Client()

    self.conversation_helper = conversation_helper
    self.prompts = {
        "first_intro":
        self.client.pull_prompt("first_session_intro"),
        "other_intro":
        self.client.pull_prompt("other_session_intro"),
        "end_session":
        self.client.pull_prompt("end_of_session"),
        "end_soon":
        self.client.pull_prompt("ending_soon"),
        "process_topics_and_character":
        self.client.pull_prompt("process_topics_and_character"),
        "process_logs":
        self.client.pull_prompt("process_logs"),
    }
    self.state: Optional[ConversationState] = None
    self.summary: Optional[str] = ""
    self.topics: List[Any] = []
    self.prompt_topics: str = ""

  def update_state(self, state: ConversationState):
    """Update the current conversation state"""
    self.state = state

  def format_hub_prompt(self, prompt_template, **variables):
    """
    Format a LangChain Hub prompt manually by extracting messages
    and replacing variables directly in message content.

    Args:
        prompt_template: A ChatPromptTemplate from hub.pull()
        **variables: Variables to format into the messages

    Returns:
        A list of formatted messages ready for the model
    """
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    # Initialize messages list
    messages = []

    # Extract messages from the template
    for msg in prompt_template.messages:
      # Get message type and content
      msg_type = msg.__class__.__name__

      # For prompt templates
      if hasattr(msg, 'prompt') and hasattr(msg.prompt, 'template'):
        template = msg.prompt.template

        # Replace variables manually
        content = template
        for var_name, var_value in variables.items():
          placeholder = '{' + var_name + '}'
          if placeholder in content:
            content = content.replace(placeholder, str(var_value))

        # Create appropriate message type
        if msg_type == 'SystemMessagePromptTemplate':
          messages.append(SystemMessage(content=content))
        elif msg_type == 'HumanMessagePromptTemplate':
          messages.append(HumanMessage(content=content))
        elif msg_type == 'AIMessagePromptTemplate':
          messages.append(AIMessage(content=content))

      # For plain messages
      elif hasattr(msg, 'content'):
        content = msg.content

        # Replace variables manually
        for var_name, var_value in variables.items():
          placeholder = '{' + var_name + '}'
          if placeholder in content:
            content = content.replace(placeholder, str(var_value))

        # Create a new message with the same type but updated content
        if isinstance(msg, SystemMessage):
          messages.append(SystemMessage(content=content))
        elif isinstance(msg, HumanMessage):
          messages.append(HumanMessage(content=content))
        elif isinstance(msg, AIMessage):
          messages.append(AIMessage(content=content))
        else:
          # Just keep the original message if type is unknown
          messages.append(msg)

    return messages

  async def handle_ending_soon(self) -> str:
    """Handle 5-minute warning only once with proper state checking"""
    if self.ending_soon_sent:
      return ""

    self.ending_soon_sent = True
    print("Generating ending soon message")

    # Check if state exists and has username
    if not self.state:
      print("Error: State is None in handle_ending_soon")
      return "Your session will end in 5 minutes."

    if not hasattr(self.state, 'username') or not self.state.username:
      print("Error: State has no username in handle_ending_soon")
      return "Your session will end in 5 minutes."

    try:
      prompt = self.prompts["end_soon"]
      prompt = prompt.invoke({"username": self.state.username})

      response = self.ai_model.invoke(prompt, config=self.model_config_time)

      if hasattr(response, 'content'):
        response_text = response.content
      elif isinstance(response, dict) and 'content' in response:
        response_text = response['content']
      else:
        response_text = str(response)

      return response_text

    except Exception as e:
      print(f"Error generating ending soon message: {e}")
      return "Your session will end in 5 minutes."

  async def handle_start(self) -> str:
    if self.chat_session.first:
      prompt = self.prompts["first_intro"]
      prompt = prompt.invoke({"username": self.state.username})
    else:
      prompt = self.prompts["other_intro"]
      prompt = prompt.invoke({
          "username": self.state.username,
          "summary": self.state.previous_summary
      })

    response = self.ai_model.invoke(prompt, config=self.model_config_time)
    response_content = response.content

    if self.state.active_topics != "":
      response_content += "\nYou have the following active topics you discussed in the recent time: " + self.state.active_topics

    return response_content

  def prepare_new_prompt_topics(self):
    for topic in self.topics:
      self.prompt_topics += f"Topic id:{topic['topic_id']}\n"  # ✅ Use dictionary key access
      self.prompt_topics += f"name:{topic['topic_name']}\n"  # ✅ Use dictionary key access
      self.prompt_topics += f"description:{topic['text']}\n"  # ✅ Use dictionary key access
      self.prompt_topics += "\n"


  async def handle_state_end(self):
    """
    Handle the end of a session, processing topics and logs using association models.
    This function:
    1. Processes the conversation topics
    2. Updates topics in the database and vector store
    3. Creates and stores conversation logs for all discussed topics
    4. Updates the session summary and user character
    """
    # Prepare prompt data from the session
    print("Starting handle_state_end")
    self.state = await self.state.prepare_prompt_end()
    print("Completed prepare_prompt_end")
    discussed_topics = await self.topic_manager.get_session_topics(
        self.state.chat_session_id)
    print(f"Discussed Topics: {discussed_topics}")

    self.chat_session.time_left = 0

    # Early return if no topics were discussed
    if not discussed_topics:
      self.summary = "You didn't discuss any topics here"
      self.chat_session.summary = self.summary

      await database_sync_to_async(self.chat_session.save)()
      print("No topics discussed; Exiting handle_state_end")
      return

    # here doesn't receive the things.
    # Get the current state
    topics = self.state.prompt_topics
    chat_history = self.state.prompt_conversation_history
    character = self.state.prompt_character

    # Step 1: Process topics and character updates
    print("Processing topics and character updates")
    topic_char_prompt = self.prompts["process_topics_and_character"].invoke({
        "topics":
        topics,
        "character":
        character,
        "chat_history":
        chat_history,
    })

    topic_char_response = await self.conversation_helper.run_until_json(
        topic_char_prompt, TopicAndCharacterJSON)
    print(f"Received topic and character response: {topic_char_response}")

    # Extract processed topics
    new_topics = topic_char_response['topics']
    self.topics = new_topics
    self.prepare_new_prompt_topics()
    print("Prepared new prompt topics")

    # Step 2: Update database and vector store
    print("Updating database and vector store")

    @database_sync_to_async
    def update_topics_in_db():
      for topic_data in new_topics:
        topic_id = topic_data["topic_id"]
        topic_name = topic_data["topic_name"]
        topic_text = topic_data["text"]

        topic_obj = Topic.objects.get(id=topic_id)
        topic_obj.name = topic_name
        topic_obj.description = topic_text
        topic_obj.date_updated = datetime.now().date()
        topic_obj.save()

    async def update_topic_vectors():
      update_tasks = []
      for topic_data in new_topics:
        topic_for_pinecone = TopicState(
            topic_id=topic_data["topic_id"],
            topic_name=topic_data["topic_name"],
            text=topic_data["text"],
            confidence=0.0,
        )
        update_tasks.append(
            self.pinecone_manager.update_topic_vector(topic_for_pinecone))
      await asyncio.gather(*update_tasks)
      print("Updated topic vectors")

    # Update user character
    print("Updating user character")

    @database_sync_to_async
    def update_character():
      profile = Profile.objects.get(user_id=self.state.user_id)
      profile.character = topic_char_response["character"]
      self.chat_session.character = profile.character
      profile.save()

    # Step 3: Process logs for each topic and build summary
    async def process_logs_for_topics():
      print("Processing logs for topics")
      logs_prompt = self.prompts["process_logs"].invoke({
          "topics": self.topics,
          "chat_history": chat_history
      })

      log_response = await self.conversation_helper.run_until_json(
          logs_prompt, LogJSON)
      print(f"Received log response: {log_response}")

      # Extract log data - now we have multiple logs
      logs_data = log_response["logs"]  # Get the array

      processed_logs = []

      # Loop through each log entry
      for log_entry in logs_data:
          log_text = log_entry["text"]
          topic_id = log_entry["topic_id"]
          topic_name = log_entry["topic_name"]

          print(f"Processing log for topic {topic_id}: {topic_name}")

          # Create log in database
          @database_sync_to_async
          def create_log_in_db():
              return Log.objects.create(
                  user_id=self.state.user_id,
                  chat_session=self.chat_session,
                  topic_id=topic_id,
                  text=log_text
              )

          # Update log in pinecone
          async def update_log_vector():
              log_for_pinecone = LogState(
                  topic_id=topic_id,
                  text=log_text,
                  topic_name=topic_name,
                  chat_session_id=self.chat_session.id
              )
              await self.pinecone_manager.upsert_log(log_for_pinecone)
              print(f"Updated log vector for topic {topic_id}")

          # Execute database and vector operations for this log
          new_log = await create_log_in_db()
          print(f"New log created in db for topic {topic_id}")
          await update_log_vector()

          # Store the processed log info
          processed_logs.append({
              "topic_id": topic_id,
              "topic_name": topic_name,
              "log_text": log_text
          })

      return processed_logs  # Return all processed logs

    # Step 4: Update session with comprehensive summary
    @database_sync_to_async
    def save_chat_session(topic_logs):
      print("Saving chat session")
      # Build a comprehensive summary of all discussed topics
      summary_parts = []
      for log_entry in topic_logs:
        topic_name = log_entry["topic_name"]
        log_text = log_entry["log_text"]
        summary_parts.append(f"{topic_name}: {log_text}")

      summary = "\n\n".join(summary_parts)

      self.summary = summary
      # Use the updated character from the AI response, not the state
      self.chat_session.character = topic_char_response["character"]
      self.chat_session.title = topic_char_response["title"]
      self.chat_session.summary = summary
      self.chat_session.save()
      print("Chat session saved")

    # Run the tasks in parallel where possible
    print("Running tasks in parallel")
    await asyncio.gather(update_topics_in_db(), update_topic_vectors(),
                         update_character())

    # Process logs and create the summary
    topic_logs = await process_logs_for_topics()
    print("Processed logs for all topics")
    await save_chat_session(topic_logs)
    print("Completed handle_state_end")

  async def handle_end(self) -> str:
    """Handle session end only once"""
    if self.session_ended:
      return ""

    self.session_ended = True
    print("Generating end session message")

    try:
      prompt = self.prompts["end_session"]
      prompt = prompt.invoke({"username": self.state.username})

      response = self.ai_model.invoke(prompt, config=self.model_config_time)

      if isinstance(response, dict) and 'content' in response:
        response_text = response['content']
      else:
        response_text = response.content if hasattr(response,
                                                    'content') else ''

      # Add hash for automatic end detection
      hash_before = "2458792345u01298347901283491234"
      response_text = hash_before + response_text

      # Add summary if available
      if hasattr(self, 'summary') and self.summary:
        response_text += f'\n\n{self.summary}'

      # Add future conversation information for first-time users
      if self.chat_session.first:
        response_text += "\n\nYour future conversations will be able to retrieve your topics and summaries from this and following conversations. You can also view them in your Moments and your profile on Focusboard"

      return response_text

    except Exception as e:
      print(f"Error generating end message: {e}")
      return "Session ended."
