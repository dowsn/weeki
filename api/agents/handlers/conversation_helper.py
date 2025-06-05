from typing import Any, Type, TypeVar, Dict, Optional, Union
import json
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Type variable for response schema types
T = TypeVar('T')


class ConversationHelper:
  """Helper class to handle common AI conversation tasks like JSON extraction"""

  def __init__(self, ai_model):
    """
        Initialize the ConversationHelper with an AI model

        Args:
            ai_model: The AI model instance that has an invoke method
        """
    self.ai_model = ai_model

  async def run_until_json(self,
                           prompt: str,
                           response_type: Type[T],
                           max_attempts: int = 3,
                           temperature: float = 0.0,
                           reasoning_effort: str = "low") -> Dict[str, Any]:
    """
      Run the model with the given prompt and extract valid JSON from the response.
      Uses LangChain's with_structured_output() method for reliable structured output.
      Makes multiple attempts if needed.
      """
    for attempt in range(max_attempts):
      try:
        # Configure model parameters
        config = {
            "configurable": {
                "foo_temperature": temperature,
                "foo_reasoning_effort": reasoning_effort
            }
        }

        # Use LangChain's structured output method
        # This handles both tool calling and JSON mode automatically
        model_with_structure = self.ai_model.with_structured_output(
            response_type,
            method=
            "function_calling"  # or "json_mode" depending on your preference
        )

        # Invoke the model with structured output
        structured_response = await model_with_structure.ainvoke(
            prompt, config=config)

        # Convert Pydantic object to dictionary if needed
        if hasattr(structured_response, 'dict'):
          return structured_response.dict()
        elif hasattr(structured_response, 'model_dump'):
          return structured_response.model_dump()
        elif isinstance(structured_response, dict):
          return structured_response
        else:
          # Convert to dict using the response_type's field annotations
          return {
              field: getattr(structured_response, field, "")
              for field in response_type.__annotations__.keys()
          }

      except Exception as e:
        logging.warning(
            f"Structured output attempt {attempt+1} failed: {str(e)}")

      # If structured output fails, try with a more explicit prompt
      if attempt < max_attempts - 1:
        # Make the requirements more explicit for next attempt
        field_descriptions = []
        for field_name, field_type in response_type.__annotations__.items():
          field_descriptions.append(f"'{field_name}': {field_type.__name__}")

        prompt = f"""Please respond with a JSON object containing exactly these fields: {{{', '.join(field_descriptions)}}}.
              
              Original request: {prompt}
              
              Return only valid JSON, no additional text."""

    # Try with JSON mode as fallback
    try:
      model_with_json = self.ai_model.with_structured_output(
          response_type, method="json_mode")
      structured_response = await model_with_json.ainvoke(prompt,
                                                          config=config)

      if hasattr(structured_response, 'dict'):
        return structured_response.dict()
      elif hasattr(structured_response, 'model_dump'):
        return structured_response.model_dump()
      elif isinstance(structured_response, dict):
        return structured_response

    except Exception as json_error:
      logging.warning(f"JSON mode fallback failed: {str(json_error)}")
      pass

    # If all attempts fail, return default values
    logging.error(
        f"Failed to get valid structured output after {max_attempts} attempts"
    )
    return {field: "" for field in response_type.__annotations__.keys()}

  def _extract_messages(self, prompt: str) -> tuple:
    """Extract system and user messages from a combined prompt."""
    # Simple implementation - you may need to adjust based on your prompt format
    lines = prompt.split('\n')
    system_lines = []
    user_lines = []

    in_system = True
    for line in lines:
      if '<query>' in line.lower():
        in_system = False

      if in_system:
        system_lines.append(line)
      else:
        user_lines.append(line)

    system_message = '\n'.join(system_lines)
    user_message = '\n'.join(user_lines)

    # If we couldn't split properly, use a default system message
    if not system_message:
      system_message = "Extract the required information in JSON format."
      user_message = prompt

    return system_message, user_message
