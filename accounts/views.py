from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.views.decorators.http import require_http_methods
from django.urls import reverse
import logging
import json

from django.contrib.auth.models import User

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

from django.views import View
from .forms import UserRegistrationForm, ProfileForm, TopicSelectionForm
from app.models import Topic, Profile





class RegistrationView(View):

  def get(self, request, step=1):
    if step == 1:
      form = UserRegistrationForm()
    elif step == 2:
      form = ProfileForm()
    elif step == 3:
      predefined_topics = predefined_topics = [
          {
              'name': 'social',
              'description':
              'This topic covers non-work social interactions, including family, friends, and romantic relationships. It encompasses social events, community service, volunteer work, clubs, cultural activities, team sports, and social media. The goal is to build meaningful connections, create a supportive network, and foster a compassionate community through personal interactions, acts of kindness, and shared experiences that promote empathy and emotional well-being.',
              'color': '#FF5733'
          },
          {
              'name': 'productive',
              'description':
              'This topic covers work, career, and income-generating activities, including job tasks, freelancing, project management, and business processes. It also encompasses household chores, DIY projects, and repairs. The scope extends to learning, skill development, financial management, health routines, and time management. The goal is to empower value creation, personal and professional growth, and efficiency, ultimately building long-term success and a purposeful life through productive endeavors and self-improvement.',
              'color': '#33FF57'
          },
          {
              'name': 'myself',
              'description':
              'This topic focuses on personal introspection and self-development, excluding casual social activities. It covers self-reflection, goal-setting, mental health practices, meditation, journaling, and self-analysis. The area includes exploring personal values, tracking progress, addressing challenges, developing self-awareness, and cultivating growth habits. Others may be referenced only as examples for insights. The goal is to nurture deep self-awareness, fostering an authentic, purposeful life through intentional self-development and introspection.',
              'color': '#3357FF'
          },
      ]
      return render(request, 'accounts/register.html', {
          'step': step,
          'predefined_topics': predefined_topics
      })
    else:
      return redirect('accounts:registration_step', step=1)
    return render(request, 'accounts/register.html', {
        'form': form,
        'step': step
    })

  def post(self, request, step=1):
    if step == 1:
      form = UserRegistrationForm(request.POST)
      if form.is_valid():
        user = form.save()
        request.session['user_id'] = user.id
        return redirect('accounts:registration_step', step=2)
      else:
        return render(request, 'accounts/register.html', {
            'form': form,
            'step': step
        })
    elif step == 2:
      user = User.objects.get(id=request.session['user_id'])
      form = ProfileForm(request.POST, instance=user.profile)
      if form.is_valid():
        form.save()
        return redirect('accounts:registration_step', step=3)
      else:
        return render(request, 'accounts/register.html', {
            'form': form,
            'step': step
        })
    elif step == 3:
      user = User.objects.get(id=request.session['user_id'])
      topics_data = json.loads(request.POST.get('topics', '[]'))

      for topic_data in topics_data:
        Topic.objects.create(
            name=topic_data['name'],
            color=topic_data['color'],
            description=topic_data['description'],
            user=user,
            active=True  # Set active to True by default
        )

      login(request, user)
      return redirect('app:week')

    return render(request, 'accounts/register.html', {
        'form': form,
        'step': step
    })


# class RegistrationView(View):

#   def get(self, request, step=1):
#     if step == 1:
#       form = UserRegistrationForm()
#     elif step == 2:
#       form = ProfileForm()
#     elif step == 3:
#       predefined_topics = [
#           {
#               'name': 'social',
#               'description':
#               'social interactions, relationships, acts of kindness and care, and community activities involving other people in a non-work related way. This topic includes family interactions, friendships, romantic relationships, social events, gatherings, community service, volunteer work, social clubs or groups, cultural events, team sports or group activities, social media interactions, networking events (non-professional), social support systems, and any activities that involve connecting with others for personal, emotional, or recreational purposes. GOAL: I value encompassesing meaningful connections and empathy, building a supportive network of relationships and fostering a more compassionate community.',
#               'color': '#FF5733'
#           },
#           {
#               'name': 'productive',
#               'description':
#               'work, job, freelance, tasks related to projects, work goals, project management or productivity-related topics, business-related processes, direct activities that earn money. Also includes household activities, DIY projects, and repairing of items. Additionally, this topic covers learning and skill development, financial management, health and fitness routines, time management strategies, and any activities that contribute to personal or professional growth and efficiency. GOAL: I empower value creation and growth, maximizing potential to build a long-term success and a purposeful life.',
#               'color': '#33FF57'
#           },
#           {
#               'name': 'myself',
#               'description':
#               'personal experiences, thoughts, self-reflection, and self-development. This topic doesn\'t involve casual social leisure activities with other people. It includes introspection, personal goal-setting, mental health practices, meditation, journaling, self-analysis, exploring personal values and beliefs, tracking personal progress, addressing personal challenges, developing self-awareness, and cultivating habits for personal growth. It may reference others only as examples for realizing insights GOAL: I nurture deep self-awareness and growth, fostering an authentic, purposeful life through intentional self-development practices and introspection.',
#               'color': '#3357FF'
#           },
#       ]
#       return render(request, 'accounts/register.html', {
#           'step': step,
#           'predefined_topics': predefined_topics
#       })
#     else:
#       return redirect('accounts:registration_step', step=1)
#     return render(request, 'accounts/register.html', {
#         'form': form,
#         'step': step
#     })

#   def post(self, request, step=1):
#     if step == 1:
#       form = UserRegistrationForm(request.POST)
#       if form.is_valid():
#         user = form.save()
#         request.session['user_id'] = user.id
#         return redirect('accounts:registration_step', step=2)
#     elif step == 2:
#       user = User.objects.get(id=request.session['user_id'])
#       form = ProfileForm(request.POST, instance=user.profile)
#       if form.is_valid():
#         form.save()
#         return redirect('accounts:registration_step', step=3)
#     elif step == 3:
#       user = User.objects.get(id=request.session['user_id'])
#       profile = user.profile

#       topics_data = json.loads(request.POST.get('topics', '[]'))

#       for topic_data in topics_data:
#         Topic.objects.create(name=topic_data['name'],
#                              color=topic_data['color'],
#                              description=topic_data['description'],
#                              user=user)

#       login(request, user)
#       return redirect('app:week')

#     return render(request, 'accounts/register.html', {
#         'form': form,
#         'step': step
#     })


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
