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
        Makes multiple attempts if needed.

        Args:
            prompt: The prompt to send to the model
            response_type: The expected response format type
            max_attempts: Maximum number of retry attempts (default: 3)
            temperature: Model temperature setting (default: 0.0)
            max_tokens: Maximum tokens for response (default: 50)
            reasoning_effort: Level of reasoning effort (default: "low")

        Returns:
            Dict containing the extracted JSON data

        Note:
            If extraction fails after max_attempts, returns an empty dict with
            default values based on the expected fields
        """
    for attempt in range(max_attempts):
      try:
        # Configure model parameters
        config = {
            "configurable": {
                "foo_temperature": temperature,
                "foo_response_format": response_type,
                "foo_reasoning_effort": reasoning_effort
            }
        }

        # Invoke the model
        response_obj = self.ai_model.invoke(prompt, config=config)
        content = response_obj.content.strip()

        # Try to find JSON in the response
        if '{' in content and '}' in content:
          json_start = content.find('{')
          json_end = content.rfind('}') + 1
          json_str = content[json_start:json_end]
          parsed = json.loads(json_str)
          return parsed
        else:
          logging.warning(f"No JSON structure found in: {content[:100]}...")

      except json.JSONDecodeError as e:
        logging.warning(f"JSON decode error on attempt {attempt+1}: {str(e)}")
      except Exception as e:
        logging.error(f"Error during JSON extraction: {str(e)}")

      # Modify prompt to be clearer about JSON requirements for the next attempt
      prompt = f"Please respond with valid JSON only. Original prompt: {prompt}"

    # If we reach here, we've failed after max_attempts
    logging.error(f"Failed to get valid JSON after {max_attempts} attempts")

    # Return empty defaults instead of raising exception
    # Try to infer default fields based on the response_type name
    if hasattr(response_type, "__annotations__"):
      # Create default values based on type annotations if available
      return {field: "" for field in response_type.__annotations__}

    # Fallback defaults
    return {"name": "", "text": ""}
