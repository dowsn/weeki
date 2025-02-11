import anthropic
from django.http import JsonResponse
from app.models import Chat_Session, Weeki, Week, Profile, Topic, User, Year, Summary, Message, PasswordResetToken, ProfileActivationToken
from smtplib import SMTPException

from django.utils import timezone
from api.utilities.regex import clean_content
import os
from django.db.models import Q
import secrets

from django.db.models.functions import TruncDate

import json
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from django.conf import settings
from .security.utils import TokenManager
from anthropic import Anthropic
from rest_framework.permissions import AllowAny
from .serializers.user_serializer import UserSerializer
from .serializers.topic_serializer import TopicSerializer
from .serializers.chat_session_serializer import Chat_SessionSerializer

from datetime import date, timedelta, datetime
from django.core.cache import cache

from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .services import get_week, get_year, get_topic, fetch_years, year_filter, topic_filter, get_current_week_id, get_object_or_error, pinecone_upsert, validate_password_strength, EmailService, validate_username, validate_email
from django.db.models import Prefetch
from django.core.exceptions import ObjectDoesNotExist

from django.db.models import Prefetch
from .utilities.utils import parse_request_data, validate_required_fields, safe_int_conversion, handle_exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView

from .serializers.summary_serializer import SummarySerializer

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render

import logging

# from api.utilities.langchain import LangchainUtility

from app.models import Conversation_Session, Conversation
from .serializers.chat_serializer import MessageSerializer
from .utilities.anthropic import AnthropicAPIUtility
from rest_framework.authtoken.models import Token
from .services import deepgram_text_to_speech

from channels.generic.http import AsyncHttpConsumer
from django.views.generic import TemplateView

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import string
import random
from datetime import datetime
import hashlib
from django.db import transaction


class CronReminder(APIView):
  permission_classes = [AllowAny]

  def get(self, request):
      # Move the database operations inside the method
      chat_sessions = Chat_Session.objects.filter(
          date=timezone.now().date() + timedelta(days=1),
          reminder_sent=False
      )

      for chat_session in chat_sessions:
          profile = Profile.objects.get(user=chat_session.user)
          email = profile.email
          EmailService.send_templated_email(
              subject="Weeki Reminder",
              context={},
              template_path="mail/reminder.html",
              recipient_email=email
          )
          chat_session.reminder_sent = True
          chat_session.save()

      return Response({"status": "success"})


def chats_view(request):

  # Check if Chat_Session for user 1 is created today
  user_id = 1

  user = User.objects.get(id=user_id)

  today = timezone.now().date()
  chat_session = Chat_Session.objects.filter(user_id=user_id,
                                             date=today).first()

  # If not created, create one
  if not chat_session:
    chat_session = Chat_Session.objects.create(user=user, date=today)
    message = 'New Chat session created'
  else:
    message = 'Existing Chat session used'

  print(message)

  # Return the chat_session id and message
  response_data = {'chat_session_id': chat_session.id, 'userId': user_id}

  return render(request, 'stream.html', response_data)


class TestMail(APIView):
  permission_classes = [AllowAny]

  def get(self, request):
    EmailService.send_templated_email(
        subject="Account Activation Code",
        template_path="mail/activation_code.html",
        context={
            "is_welcome": False,
            "token": "hi"
        },
        recipient_email="luk.meinhart@protonmail.com")


class DeleteUser(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def post(self, request):
    user_id = request.token_data['user_id']
    password = request.data.get('password')

    if not all([user_id, password]):
      return Response(
          {
              'message': 'User ID and password are required',
              'error': True
          },
          status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.get(id=user_id)

    # Verify user ID matches
    if str(user.id) != str(user_id):
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_403_FORBIDDEN)

    # Verify password
    auth_user = authenticate(username=user.username, password=password)
    if not auth_user:
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_403_FORBIDDEN)

    try:
      with transaction.atomic():
        username = user.username  # Save for logging
        user.delete()

        logger.info(f"User {username} successfully deleted their account")

        return Response({
            'content': True,
            'message': 'Account deleted successfully',
            'error': False
        })

    except Exception as e:
      logger.error(f"Error deleting user account: {str(e)}")
      return Response(
          {
              'message': 'Failed to delete account. Please try again later.',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendActivationCode(APIView):
  permission_classes = [AllowAny]

  def post(self, request):
    user_id = request.data.get('userId')
    if not user_id:
      return Response({
          'message': 'UserId is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      user = User.objects.get(id=user_id)

      cache_key = f"activation_code_limit_{user.email}"
      attempt_count = cache.get(cache_key, 0)

      if attempt_count >= 3:  # 3 requests per hour
        return Response(
            {
                'message':
                'Too many activation code requests. Please try again later.',
                'error': True
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS)

      token, _ = ProfileActivationToken.generate_token(user)

      profile = Profile.objects.get(user=user)

      if profile.activated:
        return Response({
            'message': 'Account already activated',
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)

      try:
        EmailService.send_templated_email(
            subject="Account Activation Code",
            template_path="mail/activation_code.html",
            context={
                "is_welcome": profile.welcome_mail_sent,
                "token": token
            },
            recipient_email=profile.email)

        print("here")
      except SMTPException as e:
        logger.error(
            f"SMTPException occurred while sending activation code to {profile.email}: {str(e)}"
        )

      cache.set(cache_key, attempt_count + 1, 3600)

      return Response({
          'content': True,
          'message':
          'Activation code sent successfully. Please check your email.',
          'error': False
      })

    except User.DoesNotExist:
      return Response({
          'message': 'If an account exists, an activation code will be sent.',
          'error': False
      })
    except Exception as e:
      logger.error(f"Error sending activation code: {str(e)}")
      return Response(
          {
              'message':
              'Unable to send activation code. Please try again later.',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyActivationCode(APIView):
  permission_classes = [AllowAny]

  def post(self, request):
    user_id = request.data.get('userId')
    token = request.data.get('activationCode')

    if not user_id or not token:
      return Response(
          {
              'message': 'User Id and activation code are required',
              'error': True
          },
          status=status.HTTP_400_BAD_REQUEST)

    try:
      user = User.objects.get(id=user_id)
      success, message = ProfileActivationToken.verify_token(token, user)

      if success:
        profile = Profile.objects.get(user=user)
        profile.activated = True
        profile.save()

        serializer = UserSerializer(profile, context={'request': request})
        response_data = serializer.data

        tokens = TokenManager.create_tokens(user)

        response_data['tokens'] = tokens

        return Response({
            'content': response_data,
            'message': 'Profile activated successfully',
            'error': False
        })
      else:
        return Response({
            'message': message,
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)

    except User.DoesNotExist:
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
      logger.error(f"Error verifying activation code: {str(e)}")
      return Response(
          {
              'message':
              'Unable to verify activation code. Please try again later.',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterView(APIView):
  permission_classes = [AllowAny]

  def post(self, request):
    # Get required fields
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    reminder = request.data.get('reminder')

    # Validate required fields
    if not all([username, password, email, reminder is not None]):
      return Response(
          {
              'message':
              'Username, password, email, and reminder are required',
              'error': True
          },
          status=status.HTTP_400_BAD_REQUEST)

    # Check if username exists
    if User.objects.filter(username=username).exists():
      return Response({
          'message': 'Username already exists',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    is_valid, message = validate_username(username)
    if not is_valid:
      return Response({
          'message': message,
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    is_valid, message = validate_email(email)
    if not is_valid:
      return Response({
          'message': message,
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    is_valid, message = validate_password_strength(password)
    # Ensure the password is strong
    if not is_valid:
      return Response({
          'message': message,
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    # Check if email exists in Profile
    if Profile.objects.filter(email=email).exists():
      return Response({
          'message': 'Email already registered',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = None

    try:
      with transaction.atomic():
        print("Starting user creation...")  # Debug log

        # Create user
        user = User.objects.create_user(username=username, password=password)
        print(f"User created: {user.username}")  # Debug log

        # Create profile
        profile_data = {
            'user': user,
            'email': email,
            'reminder': reminder,
            'activated': False
        }

        Profile.objects.create(**profile_data)

        return Response(
            {
                'content': user.id,
                'message': 'Registration successful. You can now login.',
                'error': False
            },
            status=status.HTTP_201_CREATED)

    except Exception as e:
      print(f"Error occurred: {str(e)}")  # Debug log
      if user is not None:
        print(f"Attempting to delete user {user.username}")  # Debug log
        try:
          user.delete()
          print("User deleted successfully")  # Debug log
        except Exception as delete_error:
          print(f"Failed to delete user: {str(delete_error)}")  # Debug log

      return Response(
          {
              'message': f'Registration failed: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateProfile(APIView):
  permission_classes = [IsAuthenticated]

  def post(self, request):
    user_id = request.token_data['user_id']

    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    reminder = request.data.get('reminder')

    # Get current user and profile
    user = get_object_or_404(User, id=user_id)
    try:
      profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
      return Response({
          'message': 'Profile not found',
          'error': True
      },
                      status=status.HTTP_404_NOT_FOUND)

    try:
      with transaction.atomic():
        # Username update and validation
        if username and username != user.username:
          if User.objects.filter(username=username).exclude(
              id=user.id).exists():
            return Response(
                {
                    'message': 'Username already exists',
                    'error': True
                },
                status=status.HTTP_400_BAD_REQUEST)
          user.username = username

          # Password update and validation

          is_valid, message = validate_username(username)
          if not is_valid:
            return Response({
                'message': message,
                'error': True
            },
                            status=status.HTTP_400_BAD_REQUEST)

        if password and password.strip():
          is_valid, message = validate_password_strength(password)
          if not is_valid:
            return Response({
                'message': message,
                'error': True
            },
                            status=status.HTTP_400_BAD_REQUEST)
          user.set_password(password)

        # Email update and validation
        if email and email != profile.email:
          if Profile.objects.filter(email=email).exclude(user=user).exists():
            return Response(
                {
                    'message': 'Email already registered',
                    'error': True
                },
                status=status.HTTP_400_BAD_REQUEST)
          profile.email = email

          is_valid, message = validate_email(email)
          if not is_valid:
            return Response({
                'message': message,
                'error': True
            },
                            status=status.HTTP_400_BAD_REQUEST)

        # Reminder update
        if reminder is not None:
          profile.reminder = reminder

        # Save changes
        user.save()
        profile.save()

        return Response({
            'message': 'Profile updated successfully',
            'error': False,
            'content': {
                'username': user.username,
                'email': profile.email,
                'reminder': profile.reminder
            }
        })

    except Exception as e:
      logger.error(f"Error updating user profile: {str(e)}")
      return Response({
          'message': 'Update failed',
          'error': True
      },
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPassword(APIView):
  permission_classes = [AllowAny]

  def post(self, request):
    email = request.data.get('email')
    if not email:
      return Response({
          'message': 'Email is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      profile = Profile.objects.get(email=email)
      user = profile.user

      # Rate limiting check
      cache_key = f"password_reset_limit_{user.email}"
      attempt_count = cache.get(cache_key, 0)

      if attempt_count >= 3:  # Limit to 3 requests per hour
        return Response(
            {
                'message':
                'Too many password reset requests. Please try again later.',
                'error': True
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS)

      # Define a stronger password policy
      alphabet = (string.ascii_uppercase + string.ascii_lowercase +
                  string.digits + "!@#$%^&*()-_+=<>?")
      temp_password = ''.join(secrets.choice(alphabet) for _ in range(16))

      # Update user's password
      user.set_password(temp_password)
      user.save()

      EmailService.send_templated_email(subject="New Password",
                                        template_path="mail/new_password.html",
                                        context={
                                            "password": temp_password,
                                            "username": user.username,
                                        },
                                        recipient_email=email)

      # Update rate limiting
      cache.set(cache_key, attempt_count + 1, 3600)  # 1 hour expiry

      return Response({
          'content': True,
          'message': 'New password has been sent to your email',
          'error': False
      })

    except User.DoesNotExist:
      # Return same message to prevent email enumeration
      return Response({
          'message':
          'If an account exists, a new password will be sent to the email address',
          'error': False
      })
    except Exception as e:
      logger.error(f"Error resetting password: {str(e)}")
      return Response(
          {
              'message': 'Unable to reset password. Please try again later.',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatSessionView(APIView):

  def delete(self, request):
    """Delete a chat session"""
    chat_session_id = request.data.get('chatSessionId')

    if not chat_session_id:
      return Response({
          'message': 'Chat session ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)
    try:
      chat_session = get_object_or_404(Chat_Session, id=chat_session_id)

      chat_session.delete()

      user = chat_session.user

      profile = Profile.objects.get(user=user)

      profile.tokens = profile.tokens + 1

      profile.save()

      return Response(
          {
              'message': 'Chat session deleted successfully',
              'error': False
          },
          status=status.HTTP_200_OK)

    except Chat_Session.DoesNotExist:
      return Response({'message': 'Chat session not found', 'error': True})

    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def post(self, request):
    """Create a new chat session"""
    user_id = request.token_data['user_id']

    try:
      date_input = request.data.get('date')
      if date_input is not None:
        try:
          date = datetime.strptime(date_input.split('T')[0], '%Y-%m-%d').date()

          if date < timezone.now().date():
            return Response(
                {
                    'message': 'Date must be in the future',
                    'error': True
                },
                status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
          logging.error(f"API Error: Invalid date input - {str(e)}")
          return Response({
              'message': 'Invalid date format',
              'error': True
          },
                          status=status.HTTP_400_BAD_REQUEST)
      else:
        logging.error("API Error: Date input is missing.")
        return Response({
            'message': 'Date is required',
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError) as e:
      logging.error(f"API Error: Invalid date input - {str(e)}")
      return Response({
          'message': 'Invalid date format',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      user = get_object_or_404(User, id=user_id)

      profile = Profile.objects.get(user=user)
      if profile.tokens <= 0:
        return Response({'message': 'Insufficient tokens', 'error': True})
      else:
        profile.tokens = profile.tokens - 1
        profile.save()

      # Check if this is the first chat session for the user by checking if there are any topics
      topic_count = Topic.objects.filter(user=user).count()

      if topic_count == 0:
        first_session = True

      # Create a new chat session
      new_chat_session = Chat_Session(user=user,
                                      date=date,
                                      first=first_session)
      new_chat_session.save()
      message = 'Chat session created successfully'

      return Response({
          'message': message,
          'error': False
      },
                      status=status.HTTP_201_CREATED)

    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def put(self, request):
    """Update an existing chat session with a new date"""
    user_id = request.token_data['user_id']
    chat_session_id = request.data.get('chatSessionId')

    # Attempt to parse the date; if an error occurs, use today's date as default

    try:
      date_input = request.data.get('date')
      if date_input is not None:
        try:
          date = datetime.strptime(date_input.split('T')[0], '%Y-%m-%d').date()

          if date < timezone.now().date():
            return Response(
                {
                    'message': 'Date must be in the future',
                    'error': True
                },
                status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
          logging.error(f"API Error: Invalid date input - {str(e)}")
          return Response({
              'message': 'Invalid date format',
              'error': True
          },
                          status=status.HTTP_400_BAD_REQUEST)
      else:
        logging.error("API Error: Date input is missing.")
        return Response({
            'message': 'Date is required',
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError) as e:
      logging.error(f"API Error: Invalid date input - {str(e)}")
      return Response({
          'message': 'Invalid date format',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    if not user_id or not chat_session_id:
      return Response(
          {
              'message': 'User ID and Chat Session ID are required',
              'error': True
          },
          status=status.HTTP_400_BAD_REQUEST)

    try:
      user = get_object_or_404(User, id=user_id)

      # Update existing chat session with new date
      chat_session = get_object_or_404(Chat_Session,
                                       id=chat_session_id,
                                       user=user)
      chat_session.date = date
      chat_session.save()
      message = 'Chat session updated successfully'

      return Response({
          'message': message,
          'error': False
      },
                      status=status.HTTP_200_OK)

    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def get_queryset(self, user, query_type=None, selected_chat_session_id=None):
    # either in past or time 0
    if selected_chat_session_id:
      return Chat_Session.objects.filter(id=selected_chat_session_id)
    else:

      thirteen_months_ago = timezone.now() - timedelta(days=390)

      return Chat_Session.objects.filter(
          user=user, time_left=0,
          date__gte=thirteen_months_ago).order_by('-date')

  def get_surrounding_chats(self, selected_chat):
    """Get the chat sessions before and after the selected chat"""
    if not selected_chat:
      return None, None

    before_chat = Chat_Session.objects.filter(
        user=selected_chat.user, time_left=0,
        date__lt=selected_chat.date).order_by('-date').first()

    after_chat = Chat_Session.objects.filter(
        user=selected_chat.user, time_left=0,
        date__gt=selected_chat.date).order_by('date').first()

    return before_chat, after_chat

  def get_all_chats(self, request):
    """Get all chats and the selected chat"""
    user_id = request.token_data['user_id']
    selected_id = request.GET.get('selectedId')

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      user = get_object_or_404(User, id=user_id)
      all_chats = self.get_queryset(user)

      data = {
          'filter': Chat_SessionSerializer(all_chats, many=True).data,
          'selectedId': selected_id
      }

      response_data = {
          'message': 'Filter for chat loaded successfully',
          'content': data,
          'error': False
      }

      return Response(response_data)

    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def get_chat_with_context(self, request):
    """Get a specific chat with its surrounding context"""
    user_id = request.token_data['user_id']
    selected_id = request.GET.get('selectedId')

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      user = get_object_or_404(User, id=user_id)

      # Get selected chat
      if selected_id:
        selected_chat = self.get_queryset(
            user, selected_chat_session_id=selected_id).first()
      else:
        selected_chat = Chat_Session.objects.filter(
            user=user, time_left=0).order_by('-date').first()

      messages = Message.objects.filter(
          chat_session=selected_chat).order_by('date_created')

      messages = MessageSerializer(messages, many=True).data,

      # Get surrounding chats
      before_chat, after_chat = self.get_surrounding_chats(selected_chat)

      data = {
          'selected':
          Chat_SessionSerializer(selected_chat).data
          if selected_chat else None,
          'messages':
          messages,
          'previousId':
          before_chat.id if before_chat else None,
          'nextId':
          after_chat.id if after_chat else None,
      }

      response_data = {
          'content': data,
          'message': 'Chat retrieved successfully',
          'error': False
      }

      return Response(response_data)

    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def get_chat_messages(self, request):
    """Get all messages for a specific chat session"""
    chat_session_id = request.GET.get('chatSessionId')

    if not chat_session_id:
      return Response({
          'message': 'Chat session ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:
      chat_session = get_object_or_404(Chat_Session, id=chat_session_id)
      messages = Message.objects.filter(
          chat_session=chat_session_id).order_by('date')

      data = {
          'messages': MessageSerializer(messages, many=True).data,
          'chatSessionId': chat_session_id
      }

      response_data = {
          'message': 'Messages retrieved successfully',
          'data': data,
          'error': False
      }

      return Response(response_data)

    except Chat_Session.DoesNotExist:
      return Response({
          'message': 'Chat session not found',
          'error': True
      },
                      status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
      return Response(
          {
              'message': f'An error occurred: {str(e)}',
              'error': True
          },
          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def get(self, request):
    user_id = request.token_data['user_id']
    """Route to appropriate method based on query parameters"""
    context = request.GET.get('context', 'false').lower() == 'true'
    getMessage = request.GET.get('getMessage', 'false').lower() == 'true'

    if getMessage:
      return self.get_chat_messages(request)
    elif context:
      return self.get_chat_with_context(request)
    else:
      return self.get_all_chats(request)


class AsyncStreamConsumer(AsyncHttpConsumer):

  async def handle(self, body):
    """Handle the streaming response"""
    await self.send_headers(headers=[
        (b"Cache-Control", b"no-cache"),
        (b"Content-Type", b"text/event-stream"),
        (b"Transfer-Encoding", b"chunked"),
    ])

    # Parse body if it exists
    query = "Who am I?"  # Default test query
    username = "Lukas"  # Default test username
    topics = [{
        "myself": "Personal development and introspection"
    }, {
        "social": "Interactions and relationships"
    }, {
        "productive": "Efficiency and task management"
    }]

    if body:
      try:
        data = json.loads(body)
        query = data.get('query', query)
        username = data.get('username', username)
        topics = data.get('topics', topics)
      except json.JSONDecodeError:
        pass

    agent = ConversationAgent(username=username, topics=topics)

    try:
      async for token in agent.generate_response(query):
        await self.send_body(
            f"data: {json.dumps({'token': token})}\n\n".encode("utf-8"),
            more_body=True)
    except Exception as e:
      await self.send_body(
          f"data: {json.dumps({'error': str(e)})}\n\n".encode("utf-8"),
          more_body=True)
    finally:
      await self.send_body(b"", more_body=False)

  # async def post(self, request):

  #   stream = True

  #   # data = json.loads(request.body)
  #   # query = data.get('query')

  #   # username = data.get('username')

  #   # topics = data.get('topics', [])

  #   query = "Who am I?"

  #   username = "Lukas"

  #   topics = [{
  #       "myself": "Personal development and introspection"
  #   }, {
  #       "social": "Interactions and relationships"
  #   }, {
  #       "productive": "Efficiency and task management"
  #   }]

  #   # Initialize conversation agent
  #   agent = ConversationAgent(username=username, topics=topics)

  #   if stream:
  #     # Generate streaming response
  #     async def response_stream():
  #       try:
  #         async for token in agent.generate_response(query):
  #           print(f"Received token: {token}")  # Print the token for debugging
  #           yield f"data: {json.dumps({'token': token})}\n\n"
  #       except Exception as e:
  #         yield f"data: {json.dumps({'error': str(e)})}\n\n"

  #     return StreamingHttpResponse(response_stream(),
  #                                  content_type='text/event-stream')
  #   else:
  #     # Generate non-streaming response
  #     response = agent.invoke_messages(query)
  #     return JsonResponse({'response': response})

  # print("GET")

  # langchain_util = LangchainUtility()

  # # For streaming output
  # langchain_util.stream_messages({"flavour": "strawberry"})


class TestSound(APIView):

  def post(self, request):

    text = request.data.get('text')
    if text:
      deepgram_text_to_speech(text)
      return Response({'status': 'success'})
    else:
      return Response({'status': 'error'})


class DashboardView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def get(self, request):

    # security??
    user_id = request.token_data['user_id']

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.get(id=user_id)

    if user:

      profile = Profile.objects.get(user=user)

      subscription_day = profile.subscription_date.day if profile.subscription_date and profile.subscription_date > timezone.now(
      ).date() else None
      next_month_number = (timezone.now().month % 12) + 1
      next_date = f"{subscription_day}.{next_month_number}." if subscription_day else "Subscribe"

      today = timezone.now().date()

      chat_session_queryset = Chat_Session.objects.filter(
          user=user, time_left__gt=0).order_by('date')[:1]

      is_already_session = Chat_Session.objects.filter(user=user,
                                                       time_left=0,
                                                       date=today).exists()

      has_expired_session = Chat_Session.objects.filter(user=user,
                                                        time_left=0).exists()

      chat_session = (Chat_SessionSerializer(chat_session_queryset.first(),
                                             many=False).data
                      if chat_session_queryset.exists() else {})

      data = {
          'next_date': next_date,
          'tokens': profile.tokens,
          'chat_session': chat_session,
          'is_already_session': is_already_session,
          'has_expired_session': has_expired_session
      }

      return Response(
          {
              'content': data,
              'message': "Topics loaded successfully",
              'error': False
          },
          status=status.HTTP_200_OK)
    else:
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_401_UNAUTHORIZED)


class TopicsView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def get(self, request):

    # security??
    user_id = request.token_data['user_id']

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.get(id=user_id)

    if user:

      three_months_ago = timezone.now() - timedelta(days=90)

      thirteen_months_ago = timezone.now() - timedelta(days=390)

      active_topics = Topic.objects.filter(user=user, )

      topics = active_topics.filter(date_updated__gt=three_months_ago, active=True)
      old_topics = active_topics.filter(date_updated__gt=thirteen_months_ago,
                                        date_updated__lte=three_months_ago, active=True)
      # Serialize if needed
      topics_data = TopicSerializer(topics, many=True).data
      old_topics_data = TopicSerializer(old_topics, many=True).data

      profile = Profile.objects.get(user=user)

      data = {
          'topics': topics_data,
          'old_topics': old_topics_data,
          'character': profile.character
      }

      return Response(
          {
              'content': data,
              'message': "Topics loaded successfully",
              'error': False
          },
          status=status.HTTP_200_OK)
    else:
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_401_UNAUTHORIZED)


class LoginAPIView(APIView):
  permission_classes = [AllowAny]

  def post(self, request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
      return Response(
          {
              'message': 'Both username and password are required',
              'error': True
          },
          status=status.HTTP_400_BAD_REQUEST)

    # Check if account is locked
    if self.is_account_locked(username):
      return Response(
          {
              'message':
              'Account temporarily locked. Please try again in 60 minutes.',
              'error': True,
              'remainingAttempts': 0,
              'lockoutTime': self.get_lockout_remaining_time(username)
          },
          status=status.HTTP_403_FORBIDDEN)

    user = authenticate(username=username, password=password)

    if user:
      try:
        # Clear failed attempts on successful login
        self.clear_failed_attempts(username)

        tokens = TokenManager.create_tokens(user)
        profile = Profile.objects.filter(user=user).first()

        if not profile:
          return Response({
              'message': 'Profile not found',
              'error': True
          },
                          status=status.HTTP_404_NOT_FOUND)

        serializer = UserSerializer(profile, context={'request': request})
        response_data = serializer.data

        response_data['tokens'] = tokens

        return Response(
            {
                'content': response_data,
                'message': "User authenticated successfully",
                'error': False
            },
            status=status.HTTP_200_OK)
      except Exception as e:
        print(f"Authentication error: {str(e)}")  # For debugging
        return Response(
            {
                'message': 'Error during authentication',
                'error': True
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
      # Record failed attempt and get remaining attempts
      remaining_attempts = self.record_failed_attempt(username)

      message = 'Invalid credentials'
      if remaining_attempts > 0:
        message = f'Invalid credentials. {remaining_attempts} attempts remaining'
      elif remaining_attempts == 0:
        message = 'Account locked due to too many failed attempts. Please try again in 60 minutes.'

      return Response(
          {
              'message':
              message,
              'error':
              True,
              'remainingAttempts':
              remaining_attempts if remaining_attempts > 0 else 0,
              'lockoutTime':
              self.get_lockout_remaining_time(username)
              if remaining_attempts == 0 else None
          },
          status=status.HTTP_401_UNAUTHORIZED)

  def is_account_locked(self, username):
    """Check if account is locked due to too many failed attempts"""
    cache_key = f"login_attempts_{username}"
    attempts = cache.get(cache_key, 0)
    return attempts >= 3

  def get_lockout_remaining_time(self, username):
    """Get remaining lockout time in minutes"""
    cache_key = f"login_attempts_{username}"
    timeout = cache._cache.get(cache_key)[1] - timezone.now().timestamp()
    return int(timeout / 60) if timeout > 0 else 0

  def record_failed_attempt(self, username):
    """Record failed login attempt and return remaining attempts"""
    cache_key = f"login_attempts_{username}"
    attempts = cache.get(cache_key, 0)
    attempts += 1

    # Set or update the cache
    # If this is the 3rd attempt, it will be locked for 60 minutes
    expiry_time = 3600 if attempts >= 3 else 300  # 60 minutes for lockout, 5 minutes for attempts
    cache.set(cache_key, attempts, expiry_time)

    return 3 - attempts if attempts < 3 else 0

  def clear_failed_attempts(self, username):
    """Clear failed attempts after successful login"""
    cache_key = f"login_attempts_{username}"
    cache.delete(cache_key)


class PineconeTestView(APIView):
  permission_classes = [AllowAny]

  def get(self, request):

    pinecone_upsert()


logger = logging.getLogger(__name__)

# @api_view(['POST'])
# @authentication_classes([SessionAuthentication, BasicAuthentication])
# @permission_classes([IsAuthenticated])

# update


def update_profile(request):
  try:

    user_id = request.token_data['user_id']
    logger.info(f"User ID: {user_id}")
  except AttributeError:
    logger.error("Invalid request data")
    return Response({
        'success': False,
        'message': 'Invalid request data'
    },
                    status=400)

  try:
    logger.info(f"Attempting to get profile for user_id: {user_id}")
    profile = Profile.objects.get(user_id=user_id)
    logger.info("Profile found")
  except ObjectDoesNotExist:
    logger.error(f"Profile not found for user_id: {user_id}")
    return Response({
        'success': False,
        'message': 'Profile not found'
    },
                    status=404)

  profile_fields = [f.name for f in Profile._meta.get_fields()]
  updated_fields = []

  logger.info(f"Request data: {request.data}")

  for field, value in request.data.items():
    if field in profile_fields and field != 'user_id':
      logger.info(f"Updating field: {field} with value: {value}")
      setattr(profile, field, value)
      updated_fields.append(field)

  if updated_fields:
    profile.save()
    logger.info("Profile updated successfully")
    return Response(
        {
            'success': True,
            'message': 'Profile updated successfully',
            'updated_fields': updated_fields
        },
        status=200)
  else:
    logger.info("No fields were updated")
    return Response({
        'success': False,
        'message': 'No fields were updated'
    },
                    status=200)


# see
class TopicView(APIView):

  def get(self, request):
    try:
      userId = request.data.get('userId')
      topicId = request.data.get('topicId')
      pagination = request.data.get('pagination')
      page = request.data.get('page')

      if userId is None or topicId is None or pagination is None or page is None:
        return Response({
            'message': 'Not all data',
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)

      topicObject = Topic.objects.get(id=topicId)

      if not topicObject.exists():
        return Response({
            'message': 'Topic not found',
            'error': True
        },
                        status=status.HTTP_404_NOT_FOUND)

      filter = {"user": userId, "topic": topicId}

      data = get_topic(pagination, page, filter)

      return Response({
          'message': 'Topic found',
          'content': data,
          'error': False
      }), status.HTTP_200_OK

    except Exception as e:
      return Response({
          'message': str(e),
          'error': True
      },
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WeekView(APIView):

  def get(self, request):
    try:
      userId = request.data.get('userId')
      pagination = request.data.get('pagination')
      page = request.data.get('page')
      weekId = request.data.get('weekId')

      if userId is None or pagination is None or page is None:
        return Response({
            'message': 'Not all data',
            'error': True
        },
                        status=status.HTTP_400_BAD_REQUEST)

      # return Response({'message': 'Week not found', 'error': True})

      if weekId is None:
        today = timezone.now().date()

        weekObject = Week.objects.filter(date_start__lte=today,
                                         date_end__gte=today).first
        weekId = weekObject.id

      else:
        weekObject = Week.objects.filter(id=weekId)

      if not weekObject.exists():
        return Response({
            'message': 'Week not found',
            'error': True
        },
                        status=status.HTTP_404_NOT_FOUND)

      filter = {'user': userId, 'week': weekId}

      weekis = get_week(pagination, page, filter)

      data = {
          'selected_week_id':
          weekObject.id,
          'week_title':
          f"Start: {weekObject.date_start.strftime('%Y-%m-%d')}, "
          f"End: {weekObject.date_end.strftime('%Y-%m-%d')}, "
          f"Year: {weekObject.year.value}",
          'weekis':
          weekis
      }

    except Exception as e:
      return Response({
          'message': str(e),
          'error': True
      },
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            'content': data,
            'message': "Week details retrieved successfully",
            'error': False
        },
        status=status.HTTP_200_OK)


class YearView(APIView):

  def get(self, request):
    try:
      userId = request.data.get('userId')
      yearId = request.data.get('yearId')

      if userId is None:
        return Response({
            'error': True,
            'message': 'User ID is required'
        },
                        status=status.HTTP_400_BAD_REQUEST)

      if yearId is None:
        current_year = timezone.now().year
        yearObject = Year.objects.filter(value=current_year)
      else:
        yearObject = Year.objects.filter(id=yearId)

      if not yearObject.exists():
        return Response({
            'message': 'Year not found',
            'error': True
        },
                        status=status.HTTP_404_NOT_FOUND)

      data = get_year(selected_year.value, userId)

      if data:
        return Response({
            'message': 'Year found',
            'content': data,
            'error': False
        }), status.HTTP_200_OK

      else:
        return Response({
            'message': 'Data not found',
            'error': True
        },
                        status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
      return Response({
          'message': str(e),
          'error': True
      },
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WeekFilter(APIView):

  def get(self, request):

    year = request.data.get('year')

    if (year is None):

      return Response({
          'message': 'Year is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:

      weeks = Week.objects.filter(year__value=year)

      return Response(
          {
              'content': weeks,
              'message': "Week filter retrieved successfully",
              'error': False
          },
          status=status.HTTP_200_OK)

    except Exception as e:
      return Response({'message': str(e), 'error': True})


class TopicFilter(APIView):

  def get(self, request):

    userId = request.data.get('userId')

    if (userId is None):

      return Response({
          'message': 'User is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:

      topics = topic_filter(userId)

      return Response(
          {
              'content': topics,
              'message': "Topic filter retrieved successfully",
              'error': False
          },
          status=status.HTTP_200_OK)

    except Exception as e:
      return Response({'message': str(e), 'error': True})


class YearFilter(APIView):

  def get(self, request):

    userId = request.data.get('userID')

    if (userId is None):
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    try:

      profile = Profile.objects.get(user_id=userId)

      if (profile is None):
        return Response({
            'message': 'Profile not found',
            'error': True
        },
                        status=status.HTTP_404_NOT_FOUND)

      year_of_birth = profile.date_of_birth.year
      final_age = 100

      years = year_filter(year_of_birth)

      return Response(
          {
              'content': years,
              'message': 'Year filter retrieved successfully',
              'error': False
          },
          status=status.HTTP_200_OK)

    except Exception as e:
      return Response({'message': str(e), 'error': True})


class WeekiDetailView(APIView):

  def get(self, request, pk):

    userId = request.data.get('userId')
    weekiId = request.data.get('weekiId')

    weeki = Weeki.objects.get(id=weekiId)
    topic_filter = topic_filter(userId)

    if not weeki.exists():
      return Response({
          'message': 'Weeki not found',
          'error': True
      },
                      status=status.HTTP_404_NOT_FOUND)

    context = {'weeki': weeki, 'topic_filter': topic_filter}

    if context:
      return Response({
          'message': 'Weeki found',
          'content': context,
          'error': False
      }), status.HTTP_200_OK

    else:
      return Response({'message': 'Data not found', 'error': True})


class SuggestQuestionView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def post(self, request):
    userId = request.data.get('userId')
    text = request.data.get('text')

    if userId is None or text is None:
      return Response({'error': True, 'message': 'Not all data'})

    user = User.objects.get(id=userId)

    text = clean_content(text)

    try:

      placeholders = {"text": text}

      print(placeholders)

      api_utility = AnthropicAPIUtility()

      response = api_utility.make_api_call("suggest_question", placeholders)

      return Response({'message': response, 'error': False})

    except Exception as e:
      return Response({'message': str(e), 'error': True})


class SaveNoteView(APIView):

  def post(self, request):

    userId = request.data.get('userId')
    text = request.data.get('text')
    weekId = get_current_week_id()

    print(userId, text, weekId)

    if userId is None or text is None or weekId is None:
      return Response({'error': True, 'message': 'Not all data'})

    user = User.objects.get(id=userId)

    week = get_object_or_error(Week, id=weekId)

    text = clean_content(text)

    try:

      topics = Topic.objects.filter(user_id=userId, active=True)

      topic_strings = ""
      for topic in topics:
        topic_strings += f"{topic.id} - {topic.name} - {topic.description}|"

      placeholders = {
          "content":
          text,
          "topics":
          topic_strings,
          "example":
          '''
        [
          { "1": "Content of the first block that matches topic 1" },
          { "2": "Content of the second block that matches topic 2" },
          ...
        ]
        '''
      }

      api_utility = AnthropicAPIUtility()

      response = api_utility.make_api_call("weeki_disect_and_categorize_2",
                                           placeholders)
      response_json = json.loads(response)

      # maybe write better
      for block in response_json:
        for topic_id_str, content_stripped in block.items():
          topic_id = int(topic_id_str)
          topic = get_object_or_error(Topic, id=topic_id)

          content_stripped = content_stripped.strip()

          new_weeki = {
              'user': user,
              'content': content_stripped,
              'week': week,
              'topic': topic
          }

          print(new_weeki)

          Weeki.objects.create(**new_weeki)

      return Response({'message': 'Note created successfully', 'error': False})

    except Exception as e:
      return Response({'message': str(e), 'error': True})


def getMementoMori(request):

  userId = request.GET.get('userId')

  profile = Profile.objects.get(user_id=userId)

  year_of_birth = profile.year_of_birth
  year_of_death = profile.year_of_death
  current_year = datetime.now().year

  active_weeks = fetch_active_weeks(userId)

  try:
    years = fetch_years(year_of_birth, year_of_death)
    return JsonResponse({'years': years, 'current_year': current_year})
  except ValueError as e:
    return JsonResponse({'error': str(e)}, status=400)
