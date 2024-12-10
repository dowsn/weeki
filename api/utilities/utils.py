import json
import anthropic
from django.http import JsonResponse

from app.models import ErrorLog



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





def log_error(self, request, error_message, additional_data=None):
  ErrorLog.objects.create(
      url=request.build_absolute_uri(),
      error_message=str(error_message),
      stack_trace=traceback.format_exc(),
      user=request.user if request.user.is_authenticated else None,
      additional_data=json.dumps(additional_data) if additional_data else None)
