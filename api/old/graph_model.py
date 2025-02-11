from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from langchain.tools.base import BaseTool


class SessionType(Enum):
  """Defines the type of chat session"""
  FIRST_TIME = "first_time"
  REGULAR = "regular"


class TopicState(BaseModel):
  """State of a topic during conversation"""
  id: Optional[int] = None
  name: str = Field(..., max_length=100)
  description: str = Field(..., max_length=500)
  actuality: float = Field(0.0, ge=0.0, le=1.0)
  related_logs: List[str] = Field(default_factory=list)


class ConversationState(BaseModel):
  """
    Tracks state for LangGraph workflow.
    Each field represents state that nodes in the graph may modify.
    """
  # Input state
  current_input: str = Field(default="")

  # Topic state
  topic_pool: List[TopicState] = Field(default_factory=list)
  current_focus: Optional[TopicState] = None
  needs_new_topic: bool = False
  topic_shift_detected: bool = False

  # Context state
  conversation_cache: str = ""
  retrieved_logs: List[str] = Field(default_factory=list)
  retrieved_topics: List[TopicState] = Field(default_factory=list)

  # Flow control
  session_type: SessionType = SessionType.REGULAR
  pinecone_initialized: bool = False
  needs_clarification: bool = False


  # Topic creation state
  in_topic_creation: bool = False
  topic_creation_step: int = 0
  topic_creation_complete: bool = False
  needs_user_confirmation: bool = False
  current_topic_draft: Optional[Dict] = None
  user_responses: List[str] = Field(default_factory=list)
  

  # Outputs and generation
  current_response: Optional[str] = None
  error_occurred: bool = False
  error_message: Optional[str] = None

  def __init__(self, **data):
    super().__init__(**data)
    self.tools: List[BaseTool] = []  # For LangGraph tool usage

  class Config:
    arbitrary_types_allowed = True
