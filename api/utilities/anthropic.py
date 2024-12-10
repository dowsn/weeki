import anthropic
from django.conf import settings
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from app.models import Prompt, Prompt_Debug

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PromptTemplate:
  template: str
  description: str


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

    # self.api_key = settings.XAI_API_KEY

    # self.client = anthropic.Anthropic(api_key=self.api_key,
    #                                   base_url="https://api.x.ai")

  def prepare_prompt(
      self, prompt: Union[str, PromptTemplate],
      placeholders: Union[Dict[str, Any], PromptPlaceholders]) -> str:
    if isinstance(prompt, PromptTemplate):
      template = prompt.template
    else:
      template = prompt
    if isinstance(placeholders, PromptPlaceholders):
      return template.format(**placeholders.placeholders)
    return template.format(**placeholders)

  def make_api_call(self,
                    prompt_name: Prompt,
                    placeholders: Union[Dict[str, Any], PromptPlaceholders],
                    additional_params: Optional[Dict[str, Any]] = None) -> str:

    prompt = Prompt.objects.get(name=prompt_name)

    # Prepare the prompt
    prepared_prompt = self.prepare_prompt(prompt.description, placeholders)

    # Prepare the API call parameters
    api_params = {
        "model": prompt.model.description,
        "max_tokens": prompt.max_tokens,
        "temperature": prompt.temperature,
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

      if settings.SETTINGS_DEBUG_AI is True:

        prompt_debug = {
            "request": prepared_prompt,
            "response": response,
            "prompt": prompt,
        }

        Prompt_Debug.objects.create(**prompt_debug)
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
    final_response = response.content[0].text.strip()
    print('response coming here:')
    print(final_response)

    # Default implementation: return the first message's text content
    return final_response
