import anthropic
from django.conf import settings
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from .prompts import prompt_library, PromptTemplate


@dataclass
class PromptPlaceholders:
  """
    A dataclass to represent prompt placeholders.
    This allows for any number of placeholders with any names.
    """
  placeholders: Dict[str, Any] = field(default_factory=dict)

  def __init__(self, **kwargs):
    self.placeholders = kwargs

  def __getattr__(self, name):
    return self.placeholders.get(name)


class AnthropicAPIUtility:
  """
    A utility class for making calls to the Anthropic API with customizable parameters.
    """

  def __init__(self, api_key: Optional[str] = None):
    """
        Initialize the AnthropicAPIUtility with an optional API key.

        :param api_key: The Anthropic API key. If not provided, it will be fetched from Django settings.
        """
    self.api_key = api_key or settings.ANTHROPIC_API_KEY
    self.client = anthropic.Anthropic(api_key=self.api_key)

  def prepare_prompt(
      self, prompt: Union[str, PromptTemplate],
      placeholders: Union[Dict[str, Any], PromptPlaceholders]) -> str:
    """
        Prepare the prompt by replacing placeholders with actual values.

        :param prompt: Either a string template or a PromptTemplate object.
        :param placeholders: Either a dictionary or a PromptPlaceholders object containing placeholder values.
        :return: The prepared prompt string.
        """
    if isinstance(prompt, PromptTemplate):
      template = prompt.template
    else:
      template = prompt

    if isinstance(placeholders, PromptPlaceholders):
      return template.format(**placeholders.placeholders)
    return template.format(**placeholders)

  def make_api_call(self,
                    prompt: Union[str, PromptTemplate],
                    placeholders: Union[Dict[str, Any], PromptPlaceholders],
                    model: str = "claude-3-haiku-20240307",
                    max_tokens: int = 1000,
                    temperature: float = 0.0,
                    additional_params: Optional[Dict[str, Any]] = None) -> str:
    """
        Make an API call to Anthropic with the given parameters.

        :param prompt: Either a string template, a PromptTemplate object, or a key from the prompt library.
        :param placeholders: Either a dictionary or a PromptPlaceholders object containing placeholder values.
        :param model: The Anthropic model to use (default: "claude-3-haiku-20240307").
        :param max_tokens: The maximum number of tokens in the response (default: 1000).
        :param temperature: The temperature for response generation (default: 0.0).
        :param additional_params: Any additional parameters to pass to the API call.
        :return: The processed response from the API.
        """
    # If prompt is a string key, fetch it from the prompt library
    if isinstance(prompt, str) and prompt in prompt_library._prompts:
      prompt = prompt_library.get_prompt(prompt)

    # Prepare the prompt
    prepared_prompt = self.prepare_prompt(prompt, placeholders)

    # Prepare the API call parameters
    api_params = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{
            "role": "user",
            "content": prepared_prompt
        }]
    }

    # Add any additional parameters
    if additional_params:
      api_params.update(additional_params)

    # Make the API call
    try:
      response = self.client.messages.create(**api_params)
      # Process and return the response
      return self.process_response(response)
    except Exception as e:
      # Handle any API call errors
      return f"Error making API call: {str(e)}"

  def process_response(self, response: Any) -> str:
    """
        Process the API response. Override this method for custom response handling.

        :param response: The raw response from the Anthropic API.
        :return: The processed response as a string.
        """
    # Default implementation: return the first message's text content
    return response.content[0].text.strip()
