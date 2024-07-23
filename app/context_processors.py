def add_app_variable(request):
  return {
    'app': 'app' in request.path
  }
