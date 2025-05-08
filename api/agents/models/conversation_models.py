# models/conversation_state.py
from datetime import datetime
from enum import Enum
from django.core.validators import int_list_validator
from pydantic import BaseModel
from typing import Optional, List, Dict
from django.conf import settings
from typing import Union
from pydantic import Field
import logging
from app.models import SessionTopic

# Initialize logging
logging.basicConfig(level=logging.INFO)


class TopicJSON(BaseModel):
  name: str = Field(description="Topic name")
  text: str = Field(description="Topic description")


class TopicPotentialJSON(BaseModel):
  topic_name: str = Field(description="Topic name")
  text: str = Field(description="Topic description")
  question: str = Field(description="Question about the topic")


class TopicAndCharacterJSON(BaseModel):
  topics: List[Dict[str, Union[str, str]]] = Field(
      description=
      "Array of topics with separate entries for name and description")
  character: str = Field(description="Character description")


class LogJSON(BaseModel):
  topic_id: int = Field(description="Topic ID")
  topic_name: str = Field(description="Topic name")


class TopicState(BaseModel):
  topic_id: int
  topic_name: str
  text: str
  confidence: float
  embedding: Optional[List[float]] = None
  date_updated: datetime = Field(default_factory=lambda: datetime.combine(
      datetime.now().date(), datetime.min.time()))


class LogState(BaseModel):
  topic_id: int
  topic_name: str
  date: Optional[datetime] = None
  text: str
  chat_session_id: Optional[int] = 0
  embedding: Optional[List[float]] = None  # Add this field


class ConversationState(BaseModel):

  model_config = {"arbitrary_types_allowed": True}

  username: str  # Add this
  user_id: int
  previous_summary: str = ""
  chat_session_id: int

  embedding: Optional[List[float]] = None

  current_message: str = ""
  conversation_context: str = ""
  saved_query: str = ""

  current_topics: List[TopicState] = []

  active_topics: str = ""

  topic_confirmation: int = 2
  prompt_topics: str = ""
  prompt_logs: str = ""
  prompt_conversation_history: str = ""
  prompt_query: str = ""
  potential_topic: str = ""
  prompt_asked_questions: str = ""

  confirm_topic: int = 2

  current_logs: List[LogState] = []

  # what about first opening after closed chat
  conversation_context: str = ""

  character: str = ""

  response: str = ""
  response_type: str = "message"

  def add_context(self, agent_context: dict):
    for attribute, value in agent_context.items():
      setattr(self, attribute, value)

  async def prepare_prompt_end(self):
    self.prompt_topics = ""
    discussed_topics = await SessionTopic.objects.filter(
        session_id=self.chat_session_id).all()
    for topic in discussed_topics:
      self.prompt_topics += f"Topic id:{topic.topic_id}\n"
      self.prompt_topics += f"name:{topic.topic_name}\n"
      self.prompt_topics += f"description:{topic.text}\n"

    self.prompt_topics += "\n"

  def prepare_prompt_topic(self):

    if self.prompt_asked_questions == "":
      self.prompt_asked_questions = "Asked Questions: "

    self.split_conversation_context()

  def prepare_prompt_process_message(self):
    self.prompt_topics = ""
    self.prompt_logs = ""

    if len(self.current_topics):
      self.prompt_topics = "<topics>Related Topics:\n"
      for topic in self.current_topics:
        self.prompt_topics += f"{topic.topic_name} - {topic.text}\n"
      self.prompt_topics += "</topics>\n"

    if len(self.current_logs):
      self.prompt_logs = "<logs>Related Past Logs:\n"
      for log in self.current_logs:
        self.prompt_logs += f"{log.topic_name} - {log.text}\n"
      self.prompt_logs += "</logs>\n"

    self.split_conversation_context(only_query=True)

  def split_conversation_context(self, only_query=False):
    window_size = 10000
    lines = self.conversation_context.split('\n')
    human_messages = []
    conversation_history = []
    found_assistant = False
    current_size = 0
    current_message = []

    # Process lines from bottom to top
    for line in reversed(lines):
      if found_assistant:
        if only_query:
          break

        # If this is a new message marker
        if line.startswith('Human:') or line.startswith('Assistant:'):
          # First check if adding the previous message would exceed the limit
          message_size = sum(len(l) + 1
                             for l in current_message)  # +1 for newlines

          if current_size + message_size > window_size and conversation_history:
            # If we already have some history and adding this would exceed, stop
            break

          # Otherwise add the current message and start a new one
          conversation_history.extend(reversed(current_message))
          current_size += message_size
          current_message = [line]
        else:
          # Continue building the current message
          current_message.append(line)
      else:
        if line.startswith('Assistant:'):
          found_assistant = True
          current_message = [line]
          continue
        if line.startswith('Human:'):
          human_messages.append(line[7:])

    # Don't forget to add the last message being processed
    if current_message and (not only_query or not found_assistant):
      conversation_history.extend(reversed(current_message))

    # Reverse the conversation history to get it in chronological order
    conversation_history = list(reversed(conversation_history))

    return human_messages, conversation_history

  def add_message(self, message: str):
    self.current_logs = []
    self.conversation_context += f"Human: {message}\n"
    self.current_message = message
    # self.update_char_since_check(len(message))

  def add_response(self, response: str):
    self.conversation_context += f"Assistant: {response}\n"

  async def update_embedding(self) -> None:
    try:
      self.embedding = await self.get_embedding()
    except Exception as e:
      logging.error(f"Error updating embedding: {e}")
      raise

  async def get_embedding(self) -> List[float]:
    stripped_context = self.string_for_retrieval()

    # Use the globally configured embedding model from Settings
    from llama_index.core import Settings
    embedding_model = Settings.embed_model

    if not embedding_model:
      raise ValueError("No embedding model available in Settings.embed_model")

    # The embedding model's interface might be different from what you expected
    # Most embedding models have either embed_query or get_text_embedding method
    if hasattr(embedding_model, 'embed_query'):
      embedding = embedding_model.embed_query(stripped_context)
    elif hasattr(embedding_model, 'get_text_embedding'):
      embedding = embedding_model.get_text_embedding(stripped_context)
    else:
      raise ValueError("Embedding model has no recognized embedding method")

    return embedding

  def string_for_retrieval(self) -> str:
    # Check if conversation_context exists and is not empty
    if not self.conversation_context:
      return ""

    lines = self.conversation_context.split('\n')
    messages = []
    current_message = []
    current_role = None
    total_chars = 0
    max_chars = 1000

    # Process lines from bottom to top
    for line in reversed(lines):
      line = line.strip()
      if not line:
        continue

      if line.startswith('Human:') or line.startswith('Assistant:'):
        # Save previous message if we were building one
        if current_message:
          full_message = ' '.join(reversed(current_message))
          message_size = len(full_message)
          messages.append(full_message)
          total_chars += message_size

        # Start new message
        current_role = 'Human' if line.startswith('Human:') else 'Assistant'
        content = line[len(current_role) + 1:].strip()
        current_message = [content] if content else []
      else:
        # Continue building the current message
        current_message.append(line)

      # Check if we've exceeded the character limit after adding a complete message
      if total_chars >= max_chars and messages:
        break

    # Don't forget to add the last message being processed
    if current_message:
      full_message = ' '.join(reversed(current_message))
      messages.append(full_message)

    # Combine messages and prepare for RAG
    combined_text = ' '.join(reversed(messages))
    cleaned = ' '.join(combined_text.split()).strip()

    cleaned = ''.join(c for c in cleaned if c.isprintable())

    return cleaned


# class ConversationState(BaseModel):

#     high_engagement: bool = True
#     needs_clarification: bool = False
#     clarification_questions: Optional[List[str]] = None
