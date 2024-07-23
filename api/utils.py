import json
import anthropic
from django.http import JsonResponse


def anthropic_api_call(prompt, content):
  # Initialize Anthropic client
  client = anthropic.Anthropic(
      api_key=settings.ANTHROPIC_API_KEY,  # Store this in Django settings
  )

  make_prompt(content)
  # Prepare the message for categorization

  # Make the API call
  message = client.messages.create(model="claude-3-haiku-20240307",
                                   max_tokens=1000,
                                   temperature=0,
                                   messages=[{
                                       "role": "user",
                                       "content": prompt
                                   }])

  # Extract and return the category number
  return int(message.content[0].text.strip())

def prepare_prompt(content):
  f"""You are tasked with categorizing a given text into one of three categories. The categories are:


  1 - productive: Text about work, tasks, goals, or productivity-related topics
  2 - myself: Text focused on personal experiences, thoughts, or self-reflection
  3 - social: Text related to social interactions, relationships, or community activities


  You will be provided with a text, and your task is to determine which category it best fits into. After analyzing the text, you must respond with only a single number (1, 2, or 3) corresponding to the most appropriate category. Do not include any other text, comments, or explanations in your response.

  Here is the text to categorize:

  <text>
  {content}
  </text>

  Analyze the content of the text and determine which category it best fits into. Consider the main focus and theme of the text when making your decision.

  Respond with only the number (1, 2, or 3) that corresponds to the most appropriate category. Do not include any other text in your response."""
  

def parse_request_data(request):
  """Parse request data from either JSON or POST."""
  try:
    return json.loads(request.body)
  except json.JSONDecodeError:
    return request.POST


def validate_required_fields(data, required_fields):
  """Validate required fields in the data."""
  missing_fields = [field for field in required_fields if not data.get(field)]
  if missing_fields:
    return JsonResponse(
        {'error': f"Missing required fields: {', '.join(missing_fields)}"},
        status=400)
  return None


def safe_int_conversion(value, field_name):
  """Safely convert a value to integer."""
  try:
    return int(value)
  except ValueError:
    return JsonResponse({'error': f"Invalid {field_name} provided"},
                        status=400)


def handle_exceptions(func):
  """Decorator to handle exceptions in view functions."""

  def wrapper(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      return JsonResponse({'error': str(e)}, status=500)

  return wrapper


