from django.conf import settings


def constants(request):
  return {
      'APP_NAME': settings.APP_NAME,
  }
