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

    self.model_config_time = {
        "configurable": {
            "foo_temperature": 0.6,
            "foo_reasoning_effort": "low"
        }
    }

    self.conversation_helper = conversation_helper
    self.prompts = {
        "first_intro": hub.pull("first_session_intro"),
        "other_intro": hub.pull("other_session_intro"),
        "end_session": hub.pull("end_of_session"),
        "end_soon": hub.pull("ending_soon"),
        "process_topics_and_character":
        hub.pull("process_topics_and_character"),
        "process_logs": hub.pull("process_logs:1edec672"),
    }
    self.state: Optional[ConversationState] = None
    self.summary: Optional[str] = ""
    self.topics: List[Any] = []
    self.prompt_topics: str = ""

  def update_state(self, state: ConversationState):
    """Update the current conversation state"""
    self.state = state

  async def handle_ending_soon(self) -> str:
    print("calling function")

    prompt = self.prompts["end_soon"].format(username=self.state.username)
    print("prompt", prompt)

    # give there that 5 minutes is left to prompt
    print("invoking ending soon!!!")
    response = self.ai_model.invoke(prompt, config=self.model_config_time)
    if isinstance(response, dict) and 'content' in response:
      response_text = response['content']
    else:
      response_text = ''
    return response_text

  async def handle_start(self) -> str:
    if self.chat_session.first:
      prompt = self.prompts["first_intro"].format(username=self.state.username)
    else:
      prompt = self.prompts["other_intro"].format(
          username=self.state.username, summary=self.state.previous_summary)
    response = self.ai_model.invoke(prompt, config=self.model_config_time)
    response_content = response.content

    if self.state.active_topics != "":
      response_content += "\nYou have the following active topics you discussed in the recent time: " + self.state.active_topics

    return response_content

  def prepare_new_prompt_topics(self):
    for topic in self.topics:
      self.prompt_topics += f"Topic id:{topic.topic_id}\n"
      self.prompt_topics += f"name:{topic.topic_name}\n"
      self.prompt_topics += f"description:{topic.text}\n"

      self.prompt_topics += "\n"

    #go through state and generate strings for prompt before update actually

    # give new topics and whole history and generate logs
    # those are topics and this is conversation for each topic create summary in format array [topic id, topic_name, and summary]

  async def handle_state_end(self):
    """
    Handle the end of a session, processing topics and logs
    using the new association models
    """
    # Process topics and character from the conversation
    await self.state.prepare_prompt_end()

    topics = self.state.prompt_topics
    summary = ""
    discussed_topics = await self.topic_manager.get_session_topics()

    if not discussed_topics:
      print("not topics")
      summary = "You didn't discuss any topics here"
      self.summary = summary
      self.chat_session.summary = summary
      self.chat_session.time_left = 0
      print("druhy", self.chat_session.time_left)
      await database_sync_to_async(self.chat_session.save)()
      return

    chat_history = self.state.conversation_context

    prompt = self.prompts["process_topics_and_character"].format(
        topics=topics,
        character=self.state.character,
        chat_history=chat_history)

    response = await self.conversation_helper.run_until_json(
        prompt, TopicAndCharacterJSON)
    print("response", response)

    # Update character
    self.chat_session.character = response["character"]

    # Process updated topics
    new_topics = response['topics']
    self.topics = new_topics
    self.prepare_new_prompt_topics()

    # Update topics in database and pinecone
    @database_sync_to_async
    def update_topics_in_db():
      for topic_data in new_topics:
        topic_id = topic_data["topic_id"]
        topic_name = topic_data["topic_name"]
        topic_text = topic_data["text"]

        # Update topic in database
        topic_obj = Topic.objects.get(id=topic_id)
        topic_obj.name = topic_name
        topic_obj.description = topic_text
        topic_obj.date_updated = datetime.now().date()
        topic_obj.save()

    await update_topics_in_db()

    # Update topic vectors in pinecone
    for topic_data in new_topics:
      topic_for_pinecone = TopicState(
          topic_id=topic_data["topic_id"],
          topic_name=topic_data["topic_name"],
          text=topic_data["text"],
          confidence=0.0,
      )
      await self.pinecone_manager.update_topic_vector(topic_for_pinecone)

    # Process logs
    prompt = self.prompts["process_logs"].format(topics=self.topics,
                                                 chat_history=chat_history)

    response = await self.conversation_helper.run_until_json(prompt, LogJSON)

    # tady
    # Extract log data
    log_text = response["text"]
    topic_id = response["topic_id"]
    topic_name = response["topic_name"]

    # Create log in database using the new association
    @database_sync_to_async
    def create_log_in_db():
      # Create the log
      new_log = Log.objects.create(user_id=self.state.user_id,
                                   chat_session=self.chat_session,
                                   topic_id=topic_id,
                                   text=log_text)

      return new_log

    @database_sync_to_async
    def delete_session_logs_and_topics():
      SessionLog.objects.filter(session=self.chat_session).delete()
      SessionTopic.objects.filter(session=self.chat_session).delete()

    await create_log_in_db()
    await delete_session_logs_and_topics()

    # Update log in pinecone
    log_for_pinecone = LogState(topic_id=topic_id,
                                text=log_text,
                                topic_name=topic_name,
                                chat_session_id=self.chat_session.id)
    await self.pinecone_manager.upsert_log(log_for_pinecone)

    # Prepare summary
    summary = f"{topic_name}:\n{log_text}"

    # Update session
    self.summary = summary
    self.chat_session.summary = summary
    self.chat_session.time_left = 0

    await database_sync_to_async(self.chat_session.save)()

  async def handle_end(self) -> str:
    prompt = self.prompts["end_session"].format(username=self.state.username)
    print("promptttdd", prompt)
    response = self.ai_model.invoke(prompt, config=self.model_config_time)
    if isinstance(response, dict) and 'content' in response:
      response_text = response['content']
    else:
      response_text = ''

    response_text += f'\n\n{self.summary}'
    return response_text
