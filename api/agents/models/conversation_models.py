# models/conversation_state.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict
from langchain_pinecone import PineconeEmbeddings
from django.conf import settings
from typing import Union


class TopicState(BaseModel):
  name: str
  description: str
  confidence: float
  embedding: List[float]
  date_updated: datetime


class LogState(BaseModel):
  date: datetime
  text: str


class ConversationState(BaseModel):

  def __init__(self, **data):
    super().__init__(**data)
    self.embeddings = PineconeEmbeddings(model="multilingual-e5-large",
                                         api_key=settings.PINECONE_API_KEY)

  username: str  # Add this
  user_id: int
  current_message: str = ""
  conversation_context: str = ""
  current_topics: List[TopicState] = []
  cached_topics: List[TopicState] = []
  potential_topic: Optional[TopicState] = None

  current_logs: List[LogState] = []

  embedding: Optional[List[float]] = None

  chars_since_check: int = 0
  # what about first opening after closed chat
  conversation_context: str = ""

  character: str = ""

  def add_chars(self, new_chars: int):
    self.chars_since_check += new_chars

  def add_message(self, message: str):
    self.current_logs = []
    self.conversation_context += f"Human: {message}\n"
    self.current_message = message
    if self.potential_topic is None:
      self.add_chars(len(message))

  def add_response(self, response: str):
    self.conversation_context += f"Assistant: {response}\n"
    if self.potential_topic is None:
      self.add_chars(len(response))

  async def update_embedding(self) -> None:
    try:
      self.embedding = await self.get_embedding()
    except Exception as e:
      print(f"Error updating embedding: {e}")

  async def get_embedding(self) -> List[float]:
    stripped_context = self.string_for_retrieval()
    # not awaitable?
    embedding = self.embeddings.embed_query(stripped_context)
    return embedding

  def string_for_retrieval(self):
    # not first message ever
    text = ' '.join(
        line.replace('Human:', '').replace('Assistant:', '')
        for line in self.conversation_context.split('\n')[1:] if line.strip())
    return self.prepare_for_rag(text)

  def prepare_for_rag(self, text: str, max_chars: int = 1000) -> str:
    return ''.join(c for c in ' '.join(text[:max_chars].split()).strip()
                   if c.isprintable())

  def get_windowed_messages(self):
    window_size = 10000
    return self.conversation_context[-window_size:]


# class ConversationState(BaseModel):

#     high_engagement: bool = True
#     needs_clarification: bool = False
#     clarification_questions: Optional[List[str]] = None
