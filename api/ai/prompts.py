# prompts.py

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PromptTemplate:
  template: str
  description: str


class PromptLibrary:
  """A class to manage a collection of prompt templates."""

  def __init__(self):
    self._prompts: Dict[str, PromptTemplate] = {}

  def add_prompt(self, name: str, template: str, description: str):
    """Add a new prompt template to the library."""
    self._prompts[name] = PromptTemplate(template, description)

  def get_prompt(self, name: str) -> PromptTemplate:
    """Retrieve a prompt template from the library."""
    return self._prompts[name]

  def list_prompts(self) -> Dict[str, str]:
    """List all available prompts with their descriptions."""
    return {name: prompt.description for name, prompt in self._prompts.items()}


# Initialize the prompt library with some example prompts
prompt_library = PromptLibrary()

prompt_library.add_prompt(
    "weeki_category",
    """You are tasked with categorizing a given text into one of three categories. The categories are:
1 - productive: Text about work, tasks, goals, or productivity-related topics, also household activities
2 - myself: Text focused on personal experiences, thoughts, or self-reflection, doesn't involve other people 
3 - social: Text related to social interactions, relationships, or community activities involving other people
You will be provided with a text, and your task is to determine which category it best fits into. After analyzing the text, you must respond with only a single number (1, 2, or 3) corresponding to the most appropriate category. Do not include any other text, comments, or explanations in your response.
Here is the text to categorize:
<text>
{content}
</text>
Analyze the content of the text and determine which category it best fits into. Consider the main focus and theme of the text when making your decision.
Respond with only the number (1, 2, or 3) that corresponds to the most appropriate category. Do not include any other text in your response.""",
    "Categorize a given text into one of three categories: productive, myself, or social"
)

prompt_library.add_prompt(
    "summarize",
    "Summarize the following text in {word_count} words: {content}",
    "Summarize a given text in a specified number of words")

prompt_library.add_prompt(
    "analyze_code",
    "Analyze the following {language} code and provide {analysis_type} feedback:\n\n```{language}\n{code}\n```",
    "Analyze code in a specified language and provide feedback")

prompt_library.add_prompt(
    "generate_story",
    "Write a {tone} {genre} story about {character} in {setting} during {time_period}.",
    "Generate a story with specified parameters")

prompt_library.add_prompt(
    "summarize_with_tone",
    "Summarize the following text in {word_count} words, using a {tone} tone suitable for {audience}: {content}",
    "Summarize a text with a specified tone and target audience")

# Add more prompts as needed

# Export the initialized library
__all__ = ['prompt_library']
