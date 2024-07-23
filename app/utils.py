from .models import ErrorLog, Weeki


def log_error(self, request, error_message, additional_data=None):
  ErrorLog.objects.create(
      url=request.build_absolute_uri(),
      error_message=str(error_message),
      stack_trace=traceback.format_exc(),
      user=request.user if request.user.is_authenticated else None,
      additional_data=json.dumps(additional_data) if additional_data else None)
