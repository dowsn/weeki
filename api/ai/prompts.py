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
    "weeki_disect_and_categorize",
    """You will be provided with a journal note as input. Your task is to analyze this text, identify its topics, restructure it into blocks based on those topics, and categorize each block. Here is the journal note:
<journal_note>
{content}
</journal_note>
Follow these steps to complete the task:

Carefully read through the journal note and identify the main topics (events, experiences, or issues) discussed in the text.
Create blocks of text by grouping together sentences or paragraphs that belong to the same topic. Do not change the content or wording of the original text.
For each block, determine which of the following categories it best fits into:
1 - productive: Text about work, tasks, goals, or productivity-related topics, also household activities
2 - myself: Text focused on personal experiences, thoughts, or self-reflection, doesn't involve other people
3 - social: Text related to social interactions, relationships, or community activities involving other people
At the start of each block, insert "|#|" followed by the category number (without quotation marks). For example: "|#|2" for a block categorized as "myself".
Place the "|#|" and category number immediately before the text of each block, without any additional spaces or line breaks.
Do not use additional dividers between blocks. The "|#|" and category number at the start of each block will serve as the separator.
Do not add any titles, topic names, or other comments to your output.
If you identify only one topic in the entire journal note, categorize it and return the input text with only "|#|" followed by the category number at the beginning.
Ensure that all of the original text is included in your output, just reorganized into topic-based blocks when applicable.
Do not include any explanations or meta-commentary about your process or the topics you've identified.

Provide your final output below, following the instructions above:""",
    "Analyze a journal note and categorize each block based on its topics")

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
