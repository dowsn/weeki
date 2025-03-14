# models/conversation_state.py
from datetime import datetime
from enum import Enum
from django.core.validators import int_list_validator
from pydantic import BaseModel
from typing import Optional, List, Dict
from langchain_pinecone import PineconeEmbeddings
from django.conf import settings
from typing import Union
from pydantic import Field
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)


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

  username: str  # Add this
  user_id: int
  previous_summary: str = ""

  current_message: str = ""
  conversation_context: str = ""
  saved_query: str = ""

  current_topics: List[TopicState] = []
  cached_topics: List[TopicState] = []

  active_topics: str = ""

  prompt_topics: str = ""
  prompt_logs: str = ""
  prompt_conversation_history: str = ""
  prompt_query: str = ""
  potential_topic: str = ""
  prompt_asked_questions: str = ""

  confirm_topic: int = 2

  cached_logs: List[LogState] = []
  current_logs: List[LogState] = []

  embedding: Optional[List[float]] = None
  embeddings: PineconeEmbeddings = Field(
      default_factory=lambda: PineconeEmbeddings(
          model="multilingual-e5-large", api_key=settings.PINECONE_API_KEY),
      exclude=True)

  chars_since_check: int = 0
  # what about first opening after closed chat
  conversation_context: str = ""

  character: str = ""

  response: str = ""
  response_type: str = "message"

  def add_context(self, agent_context: dict):
    for attribute, value in agent_context.items():
      setattr(self, attribute, value)

  def prepare_prompt_end(self):
    for topic in self.cached_topics:
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

    # Process lines from bottom to top
    for line in reversed(lines):
      if found_assistant:
        # Check if adding this line would exceed window size
        if only_query:
          break

        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > window_size:
          break  # Stop processing more lines
        current_size += line_size
        conversation_history.append(line)
      else:
        if line.startswith('Assistant:'):
          found_assistant = True
          continue

        if line.startswith('Human:'):
          human_messages.append(line[7:])

    # Reverse both arrays to maintain chronological order
    self.prompt_query = '\n'.join(reversed(human_messages))
    if only_query is False:
      self.prompt_conversation_history = '\n'.join(
          reversed(conversation_history))

  def add_message(self, message: str):
    self.current_logs = []
    self.conversation_context += f"Human: {message}\n"
    self.current_message = message
    self.update_char_since_check(len(message))

  def add_response(self, response: str):
    self.conversation_context += f"Assistant: {response}\n"
    self.update_char_since_check(len(response))

  def update_char_since_check(self, length: int):
    if self.potential_topic == "":
      self.chars_since_check += length
    else:
      self.chars_since_check = 0

  async def update_embedding(self) -> None:
    try:
      self.embedding = await self.get_embedding()
    except Exception as e:
      logging.error(f"Error updating embedding: {e}")
      raise

  async def get_embedding(self) -> List[float]:
    stripped_context = self.string_for_retrieval()
    # Just call the sync method directly - no await needed
    embedding = self.embeddings.embed_query(stripped_context)
    return embedding

  def string_for_retrieval(self) -> str:
    # Check if conversation_context exists and is not empty
    if not self.conversation_context:
      print("sakra")
      return ""

    # Create a safe list of non-empty lines
    lines = [
        line.replace('Human:', '').replace('Assistant:', '')
        for line in self.conversation_context.split('\n')
        if line and line.strip()
    ]

    # Skip first line if there are lines, otherwise return empty string
    if len(lines) > 1:
      text = ' '.join(lines[1:])
    else:
      text = ' '.join(lines)

    return self.prepare_for_rag(text)

  def prepare_for_rag(self, text: str, max_chars: int = 1000) -> str:
    # Handle empty text
    if not text:
      return ""

    # Ensure text is a string
    text = str(text)

    # Get the first max_chars characters
    truncated = text[:max_chars]

    # Clean and normalize the text
    cleaned = ' '.join(truncated.split()).strip()

    # Filter non-printable characters
    return ''.join(c for c in cleaned if c.isprintable())


# class ConversationState(BaseModel):

#     high_engagement: bool = True
#     needs_clarification: bool = False
#     clarification_questions: Optional[List[str]] = None
