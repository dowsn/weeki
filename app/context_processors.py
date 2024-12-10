def add_app_variable(request):
  return {'app': 'on' in request.path}
