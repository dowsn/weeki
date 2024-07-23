from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.views.decorators.http import require_http_methods
from django.urls import reverse
import logging

from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.http import JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import ensure_csrf_cookie

# from app.models import City  # Assume you have a City model
# from app.serializers import CitySerializer  # Assume you have a CitySerializer


class ProtectedView(APIView):
  permission_classes = [IsAuthenticated]

  def get(self, request):
    user = request.user
    return Response({
        "message": "This is a protected endpoint",
        "user_id": user.id,
        "username": user.username,
        "email": user.email
    })


# Create your views here.


def signup_view(request):
  if request.method == 'POST':
    signupForm = UserCreationForm(request.POST)
    if signupForm.is_valid():
      user = signupForm.save()
      login(request, user)
      return redirect('app:week')
    else:
      return render(request, 'accounts/signup.html', {'form': signupForm})
  else:
    signupForm = UserCreationForm()
    return render(request, 'accounts/signup.html', {'form': signupForm})


logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def login_view(request):
  if request.method == 'POST':
    logger.debug(f"POST data: {request.POST}")
    form = AuthenticationForm(request, data=request.POST)
    logger.debug(f"Form data: {form.data}")

    if form.is_valid():
      user = form.get_user()
      print(user)
      login(request, user)

      # Generate JWT tokens
      refresh = RefreshToken.for_user(user)
      tokens = {
          'refresh': str(refresh),
          'access': str(refresh.access_token),
      }

      # Check if it's an AJAX request
      if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(tokens)

      # Handle redirect for form-based login
      next_url = request.POST.get('next')
      if next_url:
        return redirect(next_url)
      else:
        return redirect('app:week')
    else:
      # Handle invalid form
      if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid credentials'}, status=400)
      else:
        return render(request, 'accounts/login.html', {'form': form})
  else:
    form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


# def login_view(request):
#   if request.method == 'POST':
#     loginForm = AuthenticationForm(data=request.POST)
#     if loginForm.is_valid():
#       user = loginForm.get_user()
#       login(request, user)
#       if 'next' in request.POST:
#         return redirect(request.POST.get('next'))
#       else:
#         return redirect('app:week')
#     else:
#       return render(request, 'accounts/login.html', {'form': loginForm})
#   else:
#     loginForm = AuthenticationForm()
#     return render(request, 'accounts/login.html', {'form': loginForm})


class RegisterView(APIView):

  def post(self, request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
      user = serializer.save()
      if user:
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@require_http_methods(["POST"])
def logout_view(request):
  logout(request)
  return redirect(reverse('home'))


def profile_view(request):
  return render(request, 'accounts/profile.html', {})
