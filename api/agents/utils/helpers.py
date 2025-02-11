from typing import List, Dict, Any, Union, Optional
from django.db.models import QuerySet
from datetime import datetime, timedelta
import re
from app.models import Message


def window_messages(messages: Union[QuerySet[Message], List[Dict]],
                    window_size: int = 10) -> str:
  """
    Creates windowed conversation context from messages.

    Args:
        messages: Either a QuerySet of Message objects or List of message dicts
        window_size: Number of most recent messages to include

    Returns:
        A formatted string of the conversation context
    """
  if not messages:
    return ""

  # Get recent messages based on window size
  recent_messages = messages[:window_size]

  # Build context string
  context = []
  last_role = None

  for message in recent_messages:
    # Handle both QuerySet and List[Dict] cases
    role = message.role if hasattr(message, 'role') else message['role']
    content = message.content if hasattr(message,
                                         'content') else message['content']

    # Add role prefix if role changes
    if role != last_role:
      context.append(f"{role}: {content}")
    else:
      context.append(content)

    last_role = role

  return "\n".join(context)


def format_log_entry(content: str, max_length: int = 500) -> str:
  """
    Format log entry for optimal storage and retrieval.

    Args:
        content: Raw log content
        max_length: Maximum length for the log

    Returns:
        Cleaned and formatted log entry
    """
  # Basic cleaning
  cleaned = (content.strip().replace('\n',
                                     ' ').replace('\r',
                                                  ' ').replace('\t', ' '))

  # Remove multiple spaces
  cleaned = re.sub(r'\s+', ' ', cleaned)

  # Truncate if needed
  if len(cleaned) > max_length:
    # Try to break at sentence or clause
    truncate_points = ['. ', '? ', '! ', '; ', ', ']
    for point in truncate_points:
      last_point = cleaned.rfind(point, 0, max_length - 3)
      if last_point > max_length * 0.5:  # Ensure we get a substantial portion
        return cleaned[:last_point + 1].strip()

    # If no good break point, just truncate with ellipsis
    return cleaned[:max_length - 3] + "..."

  return cleaned


def format_topic_description(content: str, max_length: int = 500) -> str:
  """
    Clean and structure topic descriptions.

    Args:
        content: Raw topic description
        max_length: Maximum length for description

    Returns:
        Formatted topic description
    """
  # Basic cleaning
  cleaned = (content.strip().replace('\n',
                                     ' ').replace('\r',
                                                  ' ').replace('\t', ' '))

  # Fix common punctuation issues
  cleaned = (cleaned.replace('  ', ' ').replace('..', '.').replace(
      ',,', ',').replace(' ,', ',').replace(' .', '.'))

  # Truncate if needed, trying to preserve complete sentences
  if len(cleaned) > max_length:
    last_period = cleaned.rfind('. ', 0, max_length - 3)
    if last_period > max_length * 0.7:  # If we can get a good portion
      return cleaned[:last_period + 1].strip()
    return cleaned[:max_length - 3] + "..."

  return cleaned


def get_time_decay_factor(date: datetime,
                          half_life_days: int = 30,
                          min_factor: float = 0.1) -> float:
  """
    Calculate time-based decay factor for relevance scoring.

    Args:
        date: Timestamp to calculate decay from
        half_life_days: Days after which relevance is halved
        min_factor: Minimum decay factor

    Returns:
        Decay factor between min_factor and 1.0
    """
  days_old = (datetime.now() - date).days
  if days_old <= 0:
    return 1.0

  decay = 0.5**(days_old / half_life_days)
  return max(min_factor, decay)


def calculate_similarity_score(score: float,
                               date: datetime,
                               base_weight: float = 0.7,
                               time_weight: float = 0.3,
                               half_life_days: int = 30) -> float:
  """
    Calculate combined relevance score using similarity and time decay.

    Args:
        score: Base similarity score
        date: Timestamp for time decay
        base_weight: Weight for similarity score
        time_weight: Weight for time decay
        half_life_days: Days for time decay calculation

    Returns:
        Combined relevance score
    """
  time_factor = get_time_decay_factor(date, half_life_days)
  return (score * base_weight) + (time_factor * time_weight)


def chunk_text(text: str,
               chunk_size: int = 1000,
               overlap: int = 100) -> List[str]:
  """
    Split long text into overlapping chunks for processing.

    Args:
        text: Text to split
        chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap

    Returns:
        List of text chunks
    """
  if len(text) <= chunk_size:
    return [text]

  chunks = []
  start = 0

  while start < len(text):
    # Get chunk with potential overlap
    chunk = text[start:start + chunk_size]

    # If not the last chunk, try to break at sentence
    if start + chunk_size < len(text):
      # Look for sentence breaks
      for separator in ['. ', '? ', '! ']:
        last_separator = chunk.rfind(separator)
        if last_separator != -1:
          chunk = chunk[:last_separator + 2]
          break

    chunks.append(chunk)

    # Move start position, accounting for overlap
    start += len(chunk) - overlap

  return chunks


def extract_key_phrases(text: str,
                        max_phrases: int = 5,
                        min_length: int = 3) -> List[str]:
  """
    Extract potential key phrases from text.

    Args:
        text: Source text
        max_phrases: Maximum number of phrases to extract
        min_length: Minimum word length for a phrase

    Returns:
        List of key phrases
    """
  # Split into sentences
  sentences = re.split('[.!?]+', text)

  # Extract noun phrases (simple approach)
  phrases = []
  for sentence in sentences:
    words = sentence.strip().split()
    if len(words) >= min_length:
      # Look for capitalized sequences
      phrase = []
      for word in words:
        if word[0].isupper() or phrase:
          phrase.append(word)
        else:
          if phrase and len(phrase) >= min_length:
            phrases.append(' '.join(phrase))
          phrase = []

  # Sort by length and return top phrases
  return sorted(list(set(phrases)), key=len, reverse=True)[:max_phrases]
