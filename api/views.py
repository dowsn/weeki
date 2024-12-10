import anthropic
from django.http import JsonResponse
from app.models import Weeki, Week, Profile, Topic, User, Year
from django.utils import timezone
from api.utilities.regex import clean_content
import os
import json

from django.conf import settings
from .security.utils import TokenManager
from anthropic import Anthropic
from rest_framework.permissions import AllowAny
from .serializers.user_serializer import UserSerializer
from .serializers.topic_serializer import TopicSerializer
from .serializers.meeting_serializer import MeetingSerializer

from datetime import date, timedelta, datetime

from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .services import get_week, get_year, get_topic, fetch_years, year_filter, topic_filter, get_current_week_id, get_object_or_error, run_flow, pinecone_upsert
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

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import StreamingHttpResponse, JsonResponse
from .agents.chat_agent import ConversationAgent
from django.shortcuts import render

import logging

# from api.utilities.langchain import LangchainUtility

from app.models import Conversation_Session, Conversation
from .serializers.chat_serialzers import MessageSerializer
from .utilities.anthropic import AnthropicAPIUtility
from rest_framework.authtoken.models import Token
from .services import deepgram_text_to_speech

from channels.generic.http import AsyncHttpConsumer
from django.views.generic import TemplateView


def chats_view(request, model):

  return render(request, 'stream.html', {'userId': '3', 'model': model})


def get_meeting(request):

  # security??
  user_id = request.GET.get('userId')

  if not user_id:
    return Response({
        'message': 'User ID is required',
        'error': True
    },
                    status=status.HTTP_400_BAD_REQUEST)

  meeting = Meeting.objects.filter(user=user, date__gt=timezone.now()).order_by('date').first()
  
  if meeting: 
    meeting_data = MeetingSerializer(meeting, many=false).data

    return Response(
        {
            'content': meeting_data,
            'message': "Meeting loaded successfully",
            'error': False
        },
        status=status.HTTP_200_OK)
  else:
    return Response({
        'content': False
        'message': 'There is no meeting',
        'error': False
    },
                    status=status.HTTP_401_UNAUTHORIZED)
  
  
    
    
  
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


class TopicsView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def get(self, request):

    # security??
    user_id = request.GET.get('userId')

    if not user_id:
      return Response({
          'message': 'User ID is required',
          'error': True
      },
                      status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.get(id=user_id)

    if user:

      topics = Topic.objects.filter(user=user, active=True)

      print(topics)

      topic_data = TopicSerializer(topics, many=True).data

      return Response(
          {
              'content': topic_data,
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

    user = authenticate(username=username, password=password)

    if user:
      if self.check_login_attempts(user):
        return Response(
            {
                'message': 'Account temporarily locked',
                'error': True
            },
            status=status.HTTP_403_FORBIDDEN)

      try:
        tokens = TokenManager.create_tokens(user)
        profile = Profile.objects.filter(user=user).first()

        if not profile:
          return Response({
              'message': 'Profile not found',
              'error': True
          },
                          status=status.HTTP_404_NOT_FOUND)

        # Serialize the profile using UserSerializer
        serializer = UserSerializer(profile, context={'request': request})

        # Add tokens to the serialized data
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
      self.record_failed_attempt(request)
      return Response({
          'message': 'Invalid credentials',
          'error': True
      },
                      status=status.HTTP_401_UNAUTHORIZED)

  def check_login_attempts(self, user):
    return False

  def record_failed_attempt(self, request):
    pass


class PineconeTestView(APIView):
  permission_classes = [AllowAny]

  def get(self, request):

    pinecone_upsert()


class ChatTestView(APIView):
  permission_classes = [AllowAny]

  def get(self, request):

    message = "Text"

    print("start")

    TWEAKS = {
        "TextInput-tP0ca": {
            "input_value": message
        },
    }

    response = run_flow(
        "", "chat", "chat", TWEAKS, "0ee69ff0-fc1b-4c3d-89f3-2ffe28f269f4",
        "AstraCS:bNWZJSkxWTQkuvljjNiGJPaE:6a0c88ee34f86ccccb70cc2adf6bc7ae05f6f94566338fa1bae050e6dcdf56a6"
    )

    # print(response)


# todo
class ConversationSessionView(APIView):
  permission_classes = [IsAuthenticated]
  authentication_classes = [JWTAuthentication]

  def post(self, request):
    session = Conversation_Session.objects.create(user=request.user)
    return Response({'conversationSessionId': session.id},
                    status=status.HTTP_201_CREATED)

  def get(self, request, session_id):
    try:
      session = Conversation_Session.objects.get(id=session_id,
                                                 user=request.user)
    except Conversation_Session.DoesNotExist:
      return Response({'error': 'Conversation session not found'},
                      status=status.HTTP_404_NOT_FOUND)

    messages = session.messages.all().order_by('date_created')
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)


class MessageView(APIView):

  def post(self, request, session_id):
    try:
      session = Conversation_Session.objects.get(id=session_id,
                                                 user=request.user)
    except Conversation_Session.DoesNotExist:
      return Response({'error': 'Conversation session not found'},
                      status=status.HTTP_404_NOT_FOUND)

    user_message = request.data.get('message')
    if not user_message:
      return Response({'error': 'Message content is required'},
                      status=status.HTTP_400_BAD_REQUEST)

    # Save user message
    Message.objects.create(conversation_session=session,
                           sender='user',
                           content=user_message)

    # Get response from ChatSessionManager
    anthropic = AnthropicAPIUtility()

    response = anthropic.make_api_call('mr_week')

    Message.objects.create(conversation_session=session,
                           sender='mr_week',
                           content=response)

    serializer = MessageSerializer(assistant_message)

    return Response(serializer.data, status=status.HTTP_201_CREATED)


logger = logging.getLogger(__name__)

# @api_view(['POST'])
# @authentication_classes([SessionAuthentication, BasicAuthentication])
# @permission_classes([IsAuthenticated])

# update


class GrokView(APIView):

  def post(self, request):

    XAI_API_KEY = settings.XAI_API_KEY
    client = Anthropic(
        api_key=XAI_API_KEY,
        base_url="https://api.x.ai",
    )
    message = client.messages.create(
        model="grok-beta",
        max_tokens=128,
        system=
        "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy.",
        messages=[
            {
                "role":
                "user",
                "content":
                "What is the meaning of life, the universe, and everything?",
            },
        ],
    )
    print(message.content)


def update_profile(request):
  try:

    user_id = request.data.get('user_id') or request.user.id
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
      final_age = profile.final_age

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
