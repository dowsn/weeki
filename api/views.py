from app.models import Chat_Session, Profile, Topic, User, Message, GooglePlaySubscription, ProfileActivationToken
from smtplib import SMTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from django.http import JsonResponse
import base64
import hmac
import hashlib
from django.utils import timezone
import secrets
from django.shortcuts import get_object_or_404
from django.conf import settings
from .security.utils import TokenManager
from .serializers.user_serializer import UserSerializer
from .serializers.topic_serializer import TopicSerializer
from .serializers.chat_session_serializer import Chat_SessionSerializer
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import timedelta, datetime
from django.core.cache import cache
from .services import validate_password_strength, EmailService, validate_username, validate_email
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import render
import logging
from .serializers.chat_serializer import MessageSerializer
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
import string
from django.db import transaction

logger = logging.getLogger(__name__)


class CronReminder(APIView):
  permission_classes = [AllowAny]

  def get(self, request):
    # Move the database operations inside the method
    chat_sessions = Chat_Session.objects.filter(date=timezone.now().date() +
                                                timedelta(days=1),
                                                reminder_sent=False)

    for chat_session in chat_sessions:
      profile = Profile.objects.get(user=chat_session.user)
      username = profile.user.username
      email = profile.email
      EmailService.send_templated_email(subject="Weeki Reminder",
                                        context={'username': username},
                                        template_path="mail/reminder.html",
                                        recipient_email=email)
      chat_session.reminder_sent = True
      chat_session.save()

    return Response({"status": "success"})


def chats_view(request):

  # Check if Chat_Session for user 1 is created today
  user_id = 1

  user = User.objects.get(pk=user_id)

  today = timezone.now().date()
  chat_session = Chat_Session.objects.filter(user_id=user_id,
                                             date=today).first()

  first = Topic.objects.filter(user=user).count() == 0

  # If not created, create one
  if not chat_session:
    print("new")
    chat_session = Chat_Session.objects.create(user=user,
                                               date=today,
                                               first=first)
    message = 'New Chat session created'
  else:

    message = 'Existing Chat session used'

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
    user_id = request.user_id
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
    if str(user.pk) != str(user_id):
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
    # Debug logging
    print(f"DEBUG: Request data: {request.data}")
    print(f"DEBUG: Request content type: {request.content_type}")

    user_id = request.data.get('first_user_id')
    print(f"DEBUG: Extracted userId: {user_id}")

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
    user_id = request.data.get('first_user_id')
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

        print("user" + str(user.pk) + " created")  # Debug log

        return Response(
            {
                'content': user.pk,
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
    user_id = request.user_id

    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    reminder = request.data.get('reminder')

    # Get current user and profile
    user = request.user
    try:
      profile = request.profile
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
              pk=user.id).exists():
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

      profile = request.profile

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
    user_id = request.user_id

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
      user = request.user

      profile = request.profile
      if profile.tokens <= 0:
        return Response({'message': 'Insufficient tokens', 'error': True})
      else:
        profile.tokens = profile.tokens - 1
        profile.save()

      # Check if this is the first chat session for the user by checking if there are any topics
      topic_count = Topic.objects.filter(user=user).count()

      first_session = False
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
    user_id = request.user_id
    chat_session_id = request.data.get('chatSessionId')

    # Attempt to parse the date; if an error occurs, use today's date as default

    try:
      date_input = request.data.get('date')
      if isinstance(date_input, str):
        # Parse the date string
        date = datetime.strptime(date_input, '%Y-%m-%d').date()
      else:
        return Response(
            {"error": "Date must be a string in YYYY-MM-DD format"},
            status=400)

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
      # else:
      #   logging.error("API Error: Date input is missing.")
      #   return Response({
      #       'message': 'Date is required',
      #       'error': True
      #   },
      # status=status.HTTP_400_BAD_REQUEST)
    # except (ValueError, TypeError) as e:
    #   logging.error(f"API Error: Invalid date input - {str(e)}")
    #   return Response({
    #       'message': 'Invalid date format',
    #       'error': True
    #   },
    #                   status=status.HTTP_400_BAD_REQUEST)

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
      # Remove the timestamp conversion - use the date directly
      thirteen_months_ago_date = thirteen_months_ago.date()

      return Chat_Session.objects.filter(
          user=user, time_left=0,
          date__gte=thirteen_months_ago_date).order_by('-date')

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
    user_id = request.user_id
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
    user_id = request.user_id
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
    user_id = request.user_id
    """Route to appropriate method based on query parameters"""
    context = request.GET.get('context', 'false').lower() == 'true'
    getMessage = request.GET.get('getMessage', 'false').lower() == 'true'

    if getMessage:
      return self.get_chat_messages(request)
    elif context:
      return self.get_chat_with_context(request)
    else:
      return self.get_all_chats(request)


class DashboardView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def get(self, request):

    # security??
    user_id = request.user_id

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = request.user

    if user:

      profile = request.profile

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
    user_id = request.user_id

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = request.user

    if user:

      three_months_ago = timezone.now() - timedelta(days=90)

      thirteen_months_ago = timezone.now() - timedelta(days=390)

      active_topics = Topic.objects.filter(user=user, active=True)

      topics = active_topics.filter(date_updated__gt=three_months_ago)
      old_topics = active_topics.filter(date_updated__lt=three_months_ago)

      # Serialize if needed
      topics_data = TopicSerializer(topics, many=True).data
      old_topics_data = TopicSerializer(old_topics, many=True).data

      profile = request.profile

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

        profile.last_login = timezone.now().strftime('%Y-%m-%d')
        profile.save()

        serializer = UserSerializer(profile, context={'request': request})
        response_data = serializer.data

        print("here")
        print(tokens)

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


# Remove the webhook functions from inside LoginAPIView class and put them at module level:


@csrf_exempt
@require_POST
def google_play_webhook(request):
  """Handle Google Play subscription webhooks"""
  try:
    # Security check: Verify the request comes from Google
    if not verify_google_signature(request):
      logger.warning("Invalid Google signature")
      return HttpResponse('Unauthorized', status=401)

    # Parse the Pub/Sub message
    data = json.loads(request.body)
    message = data.get('message', {})

    if not message:
      return HttpResponse('No message', status=400)

    # Decode the notification data
    notification_data = json.loads(
        base64.b64decode(message['data']).decode('utf-8'))

    logger.info(f"Received notification: {notification_data}")

    # Handle subscription notification
    if 'subscriptionNotification' in notification_data:
      handle_subscription_notification(
          notification_data['subscriptionNotification'])

    return HttpResponse('OK', status=200)

  except Exception as e:
    logger.error(f"Webhook error: {str(e)}")
    return HttpResponse('Error', status=500)


def verify_google_signature(request):
  """Verify that the request comes from Google using signature verification"""
  try:
    # Get the signature from headers
    signature = request.META.get('HTTP_X_GOOG_SIGNATURE')
    if not signature:
      return False

    # Get the verification token from settings
    verification_token = getattr(settings, 'GOOGLE_PUBSUB_VERIFICATION_TOKEN',
                                 '')
    if not verification_token:
      logger.error("GOOGLE_PUBSUB_VERIFICATION_TOKEN not set in settings")
      return False

    # Calculate expected signature
    expected_signature = base64.b64encode(
        hmac.new(verification_token.encode('utf-8'), request.body,
                 hashlib.sha1).digest()).decode('utf-8')

    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)

  except Exception as e:
    logger.error(f"Signature verification error: {str(e)}")
    return False


def handle_subscription_notification(subscription_data):
  """Handle different types of subscription notifications"""
  purchase_token = subscription_data['purchaseToken']
  notification_type = subscription_data['notificationType']
  subscription_id = subscription_data['subscriptionId']

  logger.info(
      f"Handling notification type {notification_type} for subscription {subscription_id}"
  )

  try:
    if notification_type in [1, 2, 4]:  # Purchased, renewed, or recovered
      handle_subscription_active(purchase_token, subscription_id)
    elif notification_type in [3, 12]:  # Canceled or revoked
      handle_subscription_canceled(purchase_token)
    elif notification_type == 13:  # Paused
      handle_subscription_paused(purchase_token)

  except Exception as e:
    logger.error(
        f"Error handling notification type {notification_type}: {str(e)}")


def handle_subscription_active(purchase_token, subscription_id):
  """Handle active subscription - simplified for single product"""

  # Verify with Google (subscription_id will always be the same)
  subscription_info = verify_subscription_with_google(purchase_token,
                                                      subscription_id)

  if not subscription_info:
    logger.error(f"Could not verify subscription: {purchase_token}")
    return

  # Get user (much simpler with single product)
  user = get_user_from_purchase_token(purchase_token)
  if not user:
    logger.error(f"Could not find user for purchase token: {purchase_token}")
    return

  # Update or create subscription record
  subscription, created = GooglePlaySubscription.objects.update_or_create(
      purchase_token=purchase_token,
      defaults={
          'user': user,
          'subscription_id':
          settings.GOOGLE_PLAY_SUBSCRIPTION_ID,  # Always the same
          'expiry_time_millis': int(subscription_info['expiryTimeMillis']),
          'auto_renewing': subscription_info.get('autoRenewing', True),
          'order_id': subscription_info.get('orderId', '')
      })

  # Update user profile
  profile, _ = Profile.objects.get_or_create(user=user)
  profile.tokens += 4
  profile.subscribed = True
  profile.subscription_date = subscription.expiry_date
  profile.save()

  logger.info(
      # f"Subscription processed for user {user.pk}: +4 tokens, expires {subscription.expiry_date}"
  )


def handle_subscription_canceled(purchase_token):
  """Handle canceled subscription"""
  try:
    subscription = GooglePlaySubscription.objects.get(
        purchase_token=purchase_token)
    subscription.auto_renewing = False
    subscription.save()
    # logger.info(f"Subscription canceled for user {subscription.user.id}")
  except GooglePlaySubscription.DoesNotExist:
    logger.error(f"Could not find subscription for token: {purchase_token}")


def handle_subscription_paused(purchase_token):
  """Handle paused subscription"""
  try:
    subscription = GooglePlaySubscription.objects.get(
        purchase_token=purchase_token)
    subscription.auto_renewing = False
    subscription.save()
    # logger.info(f"Subscription paused for user {subscription.user.id}")
  except GooglePlaySubscription.DoesNotExist:
    logger.error(f"Could not find subscription for token: {purchase_token}")


def verify_subscription_with_google(purchase_token, subscription_id):
  """Verify subscription with Google Play Developer API"""
  try:
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/androidpublisher'])

    service = build('androidpublisher', 'v3', credentials=credentials)

    result = service.purchases().subscriptions().get(
        packageName=settings.GOOGLE_PLAY_PACKAGE_NAME,
        subscriptionId=subscription_id,
        token=purchase_token).execute()

    return result

  except Exception as e:
    logger.error(f"Error verifying subscription with Google: {str(e)}")
    return None


@require_POST
def initiate_purchase(request):
  """Store user mapping before purchase starts"""
  try:
    # Get user from JWT (your middleware handles this)
    user_id = request.user_id

    # Simple approach: Store the last user who initiated purchase
    cache.set('last_purchase_user', user_id, 600)  # 10 minutes

    return JsonResponse({'status': 'ready'})

  except Exception as e:
    logger.error(f"Error in initiate_purchase: {str(e)}")
    return JsonResponse({'error': 'Failed'}, status=400)


# Then update get_user_from_purchase_token:
def get_user_from_purchase_token(purchase_token):
  try:
    subscription = GooglePlaySubscription.objects.get(
        purchase_token=purchase_token)
    return subscription.user
  except GooglePlaySubscription.DoesNotExist:
    # Get the last user who initiated a purchase
    user_id = cache.get('last_purchase_user')
    if user_id:
      try:
        return User.objects.get(pk=user_id)
      except User.DoesNotExist:
        pass

    logger.error(f"No user mapping found for purchase token: {purchase_token}")
    return None
