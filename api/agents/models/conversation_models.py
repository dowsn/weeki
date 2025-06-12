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
  title: str = Field(description="Session title")


class LogEntryJSON(BaseModel):
  topic_id: int = Field(description="Topic ID")
  topic_name: str = Field(description="Topic name")
  text: str = Field(
      description=
      "Log text, summary of conversation that is related to the topic")


class LogJSON(BaseModel):
  logs: List[LogEntryJSON]


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


class MessageState(BaseModel):
  role: str
  content: str
  show_in: bool


class ConversationState(BaseModel):

  model_config = {"arbitrary_types_allowed": True}

  username: str  # Add this
  user_id: int
  previous_summary: str = ""
  chat_session_id: int
  topic_ids: str = ""

  embedding: Optional[List[float]] = None

  current_message: str = ""
  saved_query: str = ""

  current_topics: List[TopicState] = []

  active_topics: str = ""

  messages: List[MessageState] = []

  topic_confirmation: int = 2
  topic_names: str = ""
  prompt_topics: str = ""
  prompt_logs: str = ""
  prompt_character: str = ""
  prompt_conversation_history: str = ""
  prompt_query: str = ""
  potential_topic: str = ""
  prompt_asked_questions: str = ""

  confirm_topic: int = 2

  current_logs: List[LogState] = []

  character: str = ""

  response: str = ""
  response_type: str = "message"

  def add_context(self, agent_context: dict):
    for attribute, value in agent_context.items():
      setattr(self, attribute, value)

  async def prepare_prompt_end(self):
    from channels.db import database_sync_to_async
    from app.models import SessionTopic

    self.prompt_topics = ""

    # Wrap the QuerySet operation with database_sync_to_async
    @database_sync_to_async
    def get_session_topics():
      return list(
          SessionTopic.objects.select_related('topic').filter(
              session=self.chat_session_id))

    discussed_topics = await get_session_topics()

    for topic in discussed_topics:
      self.prompt_topics += f"Topic id:{topic.topic.id}\n"  # Access through the foreign key
      self.prompt_topics += f"name:{topic.topic.name}\n"  # Access the name field of the related Topic
      self.prompt_topics += f"description:{topic.topic.description}\n"  # Access description of the related Topic
    self.prompt_topics += "\n"

    self.prompt_conversation_history = self.get_complete_conversation_history()

    if self.character != "":
      self.prompt_character = f"<character>{self.character}</character>\n"
    else:
      self.prompt_character = ""

    return self

  # def prepare_prompt_topic(self):

  #   # For first-time entry to topic exploration, use saved_query
  #   # For subsequent interactions within topic exploration, use current_message
  #   if self.saved_query and self.current_message == self.saved_query:
  #     self.prompt_query = self.saved_query
  #   else:
  #     self.prompt_query = self.current_message

  # Don't use conversation history in topic mode
  # self.prompt_conversation_history = ""

  def prepare_topics_to_prompt(self):
    self.prompt_topics = ""

    if len(self.current_topics):
      self.prompt_topics = "<topics>Related Topics:\n"
      for topic in self.current_topics:
        self.prompt_topics += f"{topic.topic_name} - {topic.text}\n"
      self.prompt_topics += "</topics>\n"

  def prepare_logs_to_prompt(self):
    self.prompt_logs = ""
    if len(self.current_logs):
      self.prompt_logs = "<logs>Related Past Logs:\n"
      for log in self.current_logs:
        self.prompt_logs += f"{log.topic_name} - {log.text}\n"
      self.prompt_logs += "</logs>\n"

  def prepare_prompt_process_message(self):
    self.prompt_logs = ""

    # Set up topics section

    self.prepare_topics_to_prompt()
    self.prepare_logs_to_prompt()

    self.prompt_character = f"<character>{self.character}</character>\n" if self.character else ""

    # Normal processing - get conversation history
    # Note we're using only_query=False to get both query and history
    self.split_messages(window_size=10000)

  # def get_short_conversation_context(self):
  #   """
  #   Gets a shortened version of the conversation context.
  #   Improved to correctly handle multi-line messages and remove topic exploration loops.
  #   """
  #   if self.messages is None:
  #     return ""

  #   # Parse the conversation into complete messages
  #   messages = []
  #   current_content = []
  #   current_speaker = None

  #   for message in self.messages:
  #     line = line.strip()
  #     if not line:
  #       continue

  #     if line.startswith('Human:') or line.startswith('Assistant:'):
  #       # If we were building a message, complete it
  #       if current_speaker and current_content:
  #         messages.append({
  #             "role":
  #             current_speaker,
  #             "content":
  #             ' '.join(current_content).replace('***', '')
  #         })
  #         current_content = []

  #       # Start new message
  #       current_speaker = "Human" if line.startswith('Human:') else "Assistant"
  #       content = line[len(current_speaker) + 1:].replace('***', '').strip()
  #       if content:
  #         current_content.append(content)
  #     else:
  #       # Continue building the current message
  #       current_content.append(line)

  #   # Add the last message
  #   if current_speaker and current_content:
  #     messages.append({
  #         "role": current_speaker,
  #         "content": ' '.join(current_content).replace('***', '')
  #     })

  #   # Filter out topic exploration loops
  #   filtered_messages = []
  #   in_exploration_loop = False
  #   exploration_marker = "Do you want to explore this topic further? Do you want to save it? Or do you want to leave the exploration of the topic and go on with the conversation"

  #   for message in messages:
  #     if exploration_marker in message["content"]:
  #       # If we encounter an exploration marker, toggle the state
  #       in_exploration_loop = not in_exploration_loop
  #       # Skip this message (don't add it to filtered messages)
  #       continue

  #     if not in_exploration_loop:
  #       # Only keep messages that are not part of a topic exploration loop
  #       filtered_messages.append(message)

  #   # Now process messages for short context
  #   formatted_messages = []
  #   total_chars = 0
  #   max_chars = 1000

  #   # Process messages from newest to oldest (using the filtered list)
  #   for message in reversed(filtered_messages):
  #     full_formatted_message = f"{message['role']}: {message['content']}"
  #     message_size = len(full_formatted_message)

  #     # Only add if we won't exceed character limit
  #     if total_chars + message_size <= max_chars:
  #       formatted_messages.append(full_formatted_message)
  #       total_chars += message_size
  #     else:
  #       # We've reached the character limit
  #       break

  #   # Reverse to get chronological order
  #   formatted_messages = list(reversed(formatted_messages))

  #   self.prompt_short_conversation_context = ' '.join(formatted_messages)

  #   if self.prompt_short_conversation_context:
  #     self.prompt_short_conversation_context = f"<history>{self.prompt_short_conversation_context}</history>"

  def add_message(self, message: str):
    # self.conversation_context += f"Human: {message}\n"
    self.current_message = message

    message_state = MessageState(role="Human",
                                 content=message,
                                 show_in=self.saved_query == "")

    self.messages.append(message_state)

    # self.update_char_since_check(len(message))

  def add_response(self, response: str):
    message_state = MessageState(role="Assistant",
                                 content=response,
                                 show_in=self.saved_query == "")

    self.messages.append(message_state)

  async def update_embedding(self) -> None:
    try:
      self.embedding = await self.get_embedding()
    except Exception as e:
      logging.error(f"Error updating embedding: {e}")
      raise

  async def get_embedding(self) -> List[float]:

    # Use the globally configured embedding model from Settings
    from llama_index.core import Settings
    embedding_model = Settings.embed_model

    if not embedding_model:
      raise ValueError("No embedding model available in Settings.embed_model")

    # The embedding model's interface might be different from what you expected
    # Most embedding models have either embed_query or get_text_embedding method
    emebedding_text = ""
    if self.saved_query:
      embedding_text = self.saved_query
    else:
      embedding_text = self.prompt_query

    print("embedding_text:", embedding_text)

    embedding = []
    if emebedding_text:
      if hasattr(embedding_model, 'embed_query'):
        embedding = embedding_model.embed_query(embedding_text)
      elif hasattr(embedding_model, 'get_text_embedding'):
        embedding = embedding_model.get_text_embedding(embedding_text)
      else:
        raise ValueError("Embedding model has no recognized embedding method")

    return embedding

  def split_messages(self, window_size=10000):
    """
    Simple implementation to extract prompt_query and prompt_conversation_history.
    - Uses saved_query if available, otherwise collects all consecutive human messages from bottom
    - Skips the human messages used in prompt_query when collecting history
    - Starts history collection from closest assistant message
    """
    # If saved_query exists, use it

    print(self.messages)
    if self.saved_query and self.saved_query != "":
      self.prompt_query = self.saved_query
      # When using saved_query, exclude ALL recent human messages from history
      # because they're part of the topic exploration context
      last_human_indices = []

      # Start from the end and collect consecutive human messages
      for i in range(len(self.messages) - 1, -1, -1):
        if self.messages[i].role == "Human":
          last_human_indices.append(i)
        else:
          # Stop when we hit a non-human message
          break
    else:
      # Otherwise find all consecutive human messages from the bottom
      human_messages = []
      last_human_indices = []

      # Start from the end and collect consecutive human messages
      for i in range(len(self.messages) - 1, -1, -1):
        if self.messages[i].role == "Human" and self.messages[i].show_in:
          human_messages.insert(0, self.messages[i].content)
          last_human_indices.append(i)
        else:
          # Stop when we hit a non-human message
          break

      # Join all collected human messages with a space
      self.prompt_query = " ".join(human_messages)

    # Collect messages that fit in the window, skipping the human messages used in prompt_query
    conversation_history = []
    current_size = 0

    # Start from the end and work backwards, skipping the indices in last_human_indices
    for i in range(len(self.messages) - 1, -1, -1):
      # Skip if this is one of the human messages we used in prompt_query
      if i in last_human_indices:
        continue

      if self.messages[i].show_in:

        msg = self.messages[i]
        message_text = f"{msg.role}: {msg.content}"
        message_size = len(message_text) + 1  # +1 for newline

        if current_size + message_size <= window_size:
          # Insert at beginning to maintain chronological order
          conversation_history.insert(0, message_text)
          current_size += message_size
        else:
          # Stop when we hit the window size limit
          break

    print("conversation_history", conversation_history)
    print("prompt_query", self.prompt_query)

    self.prompt_conversation_history = f"<history>{' '.join(conversation_history)}</history>" if conversation_history else ""

  def get_complete_conversation_history(self) -> str:
    """
    Returns the complete conversation history as a string,
    including the last message and only including messages with show_in=True.
    """
    # Filter messages with show_in=True

    # Format each message with its role
    formatted_messages = []
    for message in self.messages:
      formatted_messages.append(f"{message.role}: {message.content}")

    return '\n'.join(formatted_messages)
