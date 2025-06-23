from django.db.models import Prefetch
from app.models import Original_Note, Topic, Weeki, Week, Profile, Conversation_Session, User, Prompt, Conversation, Sum
# from boto3.session import Session
import os
from django.core.mail import send_mail

# from .serializers import TopicSerializer
from django.utils import timezone
from datetime import date
from rest_framework.response import Response
import json
import re
from typing import Tuple
from django.core.mail import get_connection, EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from smtplib import SMTPException

# from pinecone.grpc import PineconeGRPC as Pinecone

from collections import defaultdict
from datetime import datetime
# from .utilities.anthropic import AnthropicAPIUtility
# from nurmoai import NurmoAI
from django.utils.safestring import mark_safe

from django.db.models import F
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework import serializers
from rest_framework.utils.serializer_helpers import ReturnList, ReturnDict
from django.db.models import QuerySet
from typing import List, Dict, Any, Union
from .serializers.chat_serializer import MessageSerializer
from app.models import Message
import logging

# from deepgram import (
#     DeepgramClient,
#     SpeakOptions,
# )

#
# getting messages from the database
logger = logging.getLogger(__name__)


class EmailService:
  """Centralized email service for the application."""

  @classmethod
  def send_templated_email(cls, subject, template_path, context,
                           recipient_email):
    """
      Send an HTML email using a template.

      Args:
          subject (str): Email subject
          template_path (str): Path to the email template
          context (dict): Context data for the template
          recipient_email (str): Recipient's email address

      Returns:
          bool: True if email was sent successfully

      Raises:
          SMTPException: If there's an error sending the email
      """
    try:
      # Render HTML content
      html_content = render_to_string(template_path, context)
      text_content = strip_tags(html_content)

      # Send email
      send_mail(
          subject=subject,
          message=text_content,
          from_email=settings.DEFAULT_FROM_EMAIL,
          recipient_list=[recipient_email],
          html_message=html_content,
          fail_silently=False,
      )

      return True

    except SMTPException as e:
      logger.error(f"SMTP Error sending email to {recipient_email}: {str(e)}")
      raise
    except Exception as e:
      logger.error(
          f"Unexpected error sending email to {recipient_email}: {str(e)}",
          exc_info=True)
      raise


def get_chat_messages(
    chat_session) -> Union[ReturnList, ReturnDict, List[Dict[Any, Any]]]:
  """
  Retrieve messages for a chat session, ordered by date descending.

  Args:
      chat_session: The chat session instance to fetch messages for

  Returns:
      ReturnList, ReturnDict, or empty list of serialized messages
  """
  try:
    messages = Message.objects.filter(
        chat_session=chat_session).order_by('date_created')

    if messages:
      return MessageSerializer(messages, many=True).data
    return []

  except Exception as e:
    # Log the error appropriately in your logging system
    logger.error(
        f"Error fetching messages for chat session {chat_session.id}: {str(e)}"
    )
    return []


def validate_email(email: str) -> Tuple[bool, str]:
  """
  Validates email address format.
  Returns tuple (is_valid: bool, error_message: str)
  """
  issues = []

  if not email or len(email) > 254:
    issues.append("Email length must be between 1 and 254 characters")
    return (False, "\n".join(issues))

  # Basic pattern check
  pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
  if not re.match(pattern, email):
    issues.append("Invalid email format")
    return (False, "\n".join(issues))

  # Split into local and domain parts
  local, domain = email.split('@')

  if len(local) > 64:
    issues.append("Local part must not exceed 64 characters")

  if domain.endswith('.'):
    issues.append("Domain cannot end with a dot")

  if '..' in email:
    issues.append("Email cannot contain consecutive dots")

  if email.startswith('.'):
    issues.append("Email cannot start with a dot")

  return (len(issues) == 0, "\n".join(issues) if issues else "")


def validate_username(username: str) -> Tuple[bool, str]:
  """
  Validates username against security criteria.
  Returns tuple (is_valid: bool, error_message: str)
  """
  issues = []

  if len(username) < 3:
    issues.append("Username must be at least 3 characters")
  if len(username) > 12:
    issues.append("Username must be less than 12 characters")

  if not username[0].isalpha():
    issues.append("Username must start with a letter")

  if not re.match("^[a-zA-Z0-9_.-]*$", username):
    issues.append("Username can only contain letters, numbers, and ._-")

  if re.search(r"\.{2,}|-{2,}|_{2,}", username):
    issues.append(
        "Username cannot contain consecutive dots, dashes or underscores")

  return (len(issues) == 0, "\n".join(issues) if issues else "")


def validate_password_strength(password: str) -> Tuple[bool, str]:
  """
    Validates password strength against multiple security criteria.

    Args:
        password: The password string to validate

    Returns:
        Tuple containing:
        - Boolean indicating if password meets all criteria
        - String message explaining any failed criteria (empty if password is valid)
    """
  issues = []

  # Check minimum length (increased to 12 for better security)
  if len(password) < 12:
    issues.append("Password must be at least 12 characters long")

  if len(password) > 20:
    issues.append("Password is too long")

  # Check for uppercase letters
  if not re.search(r"[A-Z]", password):
    issues.append("Password must contain at least one uppercase letter")

  # Check for lowercase letters
  if not re.search(r"[a-z]", password):
    issues.append("Password must contain at least one lowercase letter")

  # Check for numbers
  if not re.search(r"[0-9]", password):
    issues.append("Password must contain at least one number")

  # Check for special characters (expanded set)
  if not re.search(r"[!@#$%^&*(),.?\":{}|<>~`\-_=+\[\]/\\]", password):
    issues.append("Password must contain at least one special character")

  # Check for common patterns
  if re.search(r"(.)\1{2,}", password):
    issues.append(
        "Password should not contain repeated characters (e.g., 'aaa')")

  # Check for sequential characters
  if any(
      str(password).lower().find(seq) != -1 for seq in [
          "123", "234", "345", "456", "567", "678", "789", "abc", "bcd", "cde",
          "def", "efg", "fgh", "ghi", "hij", "ijk", "jkl", "klm", "lmn", "mno",
          "nop", "opq", "pqr", "qrs", "rst", "stu", "tuv", "uvw", "vwx", "wxy",
          "xyz"
      ]):
    issues.append(
        "Password should not contain sequential characters (e.g., '123', 'abc')"
    )

  # Check for common words and patterns
  common_patterns = ["password", "admin", "user", "login", "welcome", "qwerty"]
  if any(pattern in password.lower() for pattern in common_patterns):
    issues.append(
        "Password contains common words or patterns that should be avoided")

  # Check for minimum number of unique characters
  if len(set(password)) < 8:
    issues.append("Password should contain at least 8 unique characters")

  # Calculate rough entropy score
  char_sets = [
      bool(re.search(r"[A-Z]", password)),  # uppercase
      bool(re.search(r"[a-z]", password)),  # lowercase
      bool(re.search(r"[0-9]", password)),  # digits
      bool(re.search(r"[!@#$%^&*(),.?\":{}|<>~`\-_=+\[\]/\\]",
                     password))  # special
  ]
  char_set_size = sum(96 if char_set else 0 for char_set in char_sets)
  if char_set_size * len(password) < 1000:  # rough entropy threshold
    issues.append(
        "Password is not complex enough - try mixing more types of characters")

  is_valid = len(issues) == 0
  # Join all issues with newlines if there are any, otherwise return empty string
  message = "\n".join(issues) if issues else ""

  return is_valid, message


# def pinecone_upsert():
#   pc = Pinecone(
#       api_key=
#       "pcsk_xNaso_DERNS2upCC5tP5D5uwWwGz2U5znoeT77w5Ve5foDiYRn8B4HtKBvVCri3yNYLp8"
#   )

#   # To get the unique host for an index,
#   # see https://docs.pinecone.io/guides/data/target-an-index
#   index = pc.Index(
#       host="https://weeki2-tbsytl8.svc.aped-4627-b74a.pinecone.io")

#   text = "I work as a circus man"

#   embedding = get_embedding(text)
#   print(embedding)

#   index.upsert(vectors=[{
#       "id": "A",
#       "values": embedding,
#       "metadata": {
#           "text": text,
#           "year": 2020
#       }
#   }],
#                namespace="summaries")

# def get_embedding(text,
#                   region_name='us-west-2',
#                   model_id="amazon.titan-embed-text-v2:0"):
#   """
# Generate embeddings for input text using Amazon Bedrock Titan model

# Args:
# text (str): Input text to generate embeddings for
# aws_access_key_id (str): AWS access key ID
# aws_secret_access_key (str): AWS secret access key
# aws_session_token (str): AWS session token (optional)
# region_name (str): AWS region name
# model_id (str): Bedrock model ID to use
# Returns:
# list: Embedding vector
# """
#   # Create a session with credentials
#   session = Session(aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
#                     aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
#                     region_name=region_name)

#   # Initialize Bedrock client with session
#   bedrock = session.client(service_name='bedrock-runtime')

#   # Prepare the request body
#   request_body = {"inputText": text}

#   body = json.dumps(request_body)

#   try:
#     # Call Bedrock API
#     response = bedrock.invoke_model(modelId=model_id, body=body)

#     # Parse response
#     response_body = json.loads(response['body'].read())
#     embedding = response_body['embedding']

#     return embedding

#   except Exception as e:
#     print(f"Error generating embedding: {str(e)}")
#     return None

# def run_flow(message,
#              output_type="chat",
#              input_type="chat",
#              tweaks=None,
#              langflow_id=None,
#              application_token=None):

#   BASE_API_URL = "https://api.langflow.astra.datastax.com"
#   api_url = f"{BASE_API_URL}/lf/{langflow_id}/api/v1/run/first_message"

#   payload = {
#       "input_value": message,
#       "output_type": output_type,
#       "input_type": input_type,
#   }

#   if tweaks:
#     payload["tweaks"] = tweaks

#   print(f"Payload: {payload}")

#   headers = {"Content-Type": "application/json"}

#   if application_token:
#     headers["Authorization"] = f"Bearer {application_token}"

#   response = requests.post(api_url, json=payload, headers=headers)

#   return response.json(
#   )['outputs'][0]['outputs'][0]['results']['message']['text']


def paginate_model(model_name, pagination, page, filter_kwargs=None):
  # Calculate the start and end indices for pagination
  end_index = model_name.objects.count() - (pagination * (page - 1))
  start_index = max(0, end_index - pagination)

  # Apply filtering if filter_kwargs are provided
  if filter_kwargs:
    items = model_name.objects.filter(
        **filter_kwargs).order_by('-date_created')[start_index:end_index]
  else:
    # Fetch the items using slicing
    items = model_name.objects.order_by('-date_created')[start_index:end_index]

  # Flip the items list
  items = list(reversed(items))

  return items


# def deepgram_text_to_speech(text):
#   try:

#     text_data = {"text": text}
#     timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
#     filename = "media/responses/".timestamp + ".wav"

#     deepgram = DeepgramClient(api_key=os.environ.get("DEEPGRAM_API_KEY"))
#     options = SpeakOptions(model="aura-asteria-en",
#                            encoding="linear16",
#                            container="wav")

#     # STEP 3: Call the save method on the speak property
#     response = deepgram.speak.v("1").save(filename, text_data, options)

#     return filename

#   except Exception:
#     print("Error")

#     # STEP 2: Configure the options (such as model choice, audio configuration, etc.)


def calculate_age(birth_date):
  today = date.today()
  return today.year - birth_date.year - (
      (today.month, today.day) < (birth_date.month, birth_date.day))


def calculate_life_percentage(birth_date, final_age):
  now = timezone.now().date()
  age = calculate_age(birth_date)
  total_days = final_age * 365.25  # Accounting for leap years
  days_lived = (now - birth_date).days
  percentage = (days_lived / total_days) * 100
  return round(percentage, 1)


def calculate_years_total(birth_date, final_age):
  year_of_death = birth_date.year + final_age
  years_total = year_of_death - birth_date.year
  return years_total


def fetch_years(year_of_birth, final_age):
  return list(
      reversed(range(int(year_of_birth), int(year_of_birth + final_age + 1))))


def fetch_active_weeks(userId):
  unique_week_ids = list(
      Weeki.objects.values_list('week_id', flat=True).distinct())

  active_weeks = Week.objects.filter(id__in=unique_week_ids)

  return active_weeks


def year_filter(year_of_birth):
  current_year = int(date.today().year)
  years = list(reversed(range(int(year_of_birth), current_year + 1)))
  max_index = len(years) - 1

  return [{
      'value': year,
      'index': max_index - i
  } for i, year in enumerate(years)]


def chat_with_nurmo(conversation_session_id,
                    messages,
                    user_message,
                    first=False):

  conversation_session = Conversation_Session.objects.get(
      id=conversation_session_id)

  if first == True:
    profile = Profile.objects.get(user_id=conversation_session.user_id)

    Profile.objects.filter(user_id=conversation_session.user_id).update(
        chat_sessions_available=F('chat_sessions_available') - 1)
  else:
    Profile.objects.filter(user_id=conversation_session.user_id).update(
        chats_available=F('chats_available') - 1)

  nurmo = NurmoAI('nu-vVEz3zltqmnmN82yVbVKyQgp7T4mL93jvq5ICo56yTMW6onI')

  messages.append({"role": "user", "content": user_message})

  if len(messages) > 7:
    messages.pop(0)

  Conversation.objects.create(sender='user',
                              content=user_message,
                              conversation_session=conversation_session)

  # anthropic = AnthropicAPIUtility()

  # nurmo_response = anthropic.make_api_call('mrs_week')
  nurmo_response = nurmo.create_completion(
      messages=messages,
      model="nurmo-2",
      character="78d8ebb5-8333-4d63-9599-75ee5c9ac8fe")

  if nurmo_response == {'error': 'Message limit reached for this minute.'}:
    nurmo_response = "Sorry, I have reached my limit for today. Please try again tomorrow."
  else:

    Conversation.objects.create(sender='assistant',
                                content=nurmo_response,
                                conversation_session=conversation_session)

  return nurmo_response


def prepare_first_conversation_context(user_id, topic_id):

  user = User.objects.get(id=user_id)
  topic = Topic.objects.get(id=topic_id)

  conversation_session = Conversation_Session.objects.create(user=user,
                                                             topic=topic)

  conversation_session_id = conversation_session.id

  # update chats available
  Profile.objects.filter(user=user).update(
      chat_sessions_available=F('chat_sessions_available') - 1)
  # Fetch the  most recent weekis
  weekis = Weeki.objects.filter(
      topic=topic,
      date_created__gte=timezone.now() -
      timezone.timedelta(days=7)).order_by('-date_created')

  weekis_string = ' '.join(weeki.content for weeki in weekis)

  # get previous conversation if needed

  # first chat response:

  api_utility = AnthropicAPIUtility()

  placeholders = {
      "topic": topic.name,
      "topic_description": topic.description,
      "notes": weekis_string,
      # "conversations": conversations_string,
      # "language": "English",
      "username": user.username,
  }

  prompt = Prompt.objects.get(name="mr_week")

  prompt = api_utility.prepare_prompt(prompt.description, placeholders)

  first_nurmo_response = chat_with_nurmo(conversation_session_id, [], prompt,
                                         True)

  conversations_array = []
  now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  conversations_array.append({
      'sender': 'Mr. Week',
      'content': first_nurmo_response,
      'date_created': now_str,
      'date_created_formatted': now_str
  })

  conversations_json = json.dumps(conversations_array)

  context = {
      'topic_name': topic.name,
      'conversation_session_id': conversation_session_id,
      'conversations': mark_safe(conversations_json),
  }

  return context


def get_build_context(user_id):
  user = User.objects.get(id=user_id)
  topics = Topic.objects.filter(active=True,
                                user_id=user_id).order_by('ordering')

  profile = Profile.objects.get(user_id=user_id)
  life_percentage = calculate_life_percentage(profile.date_of_birth,
                                              profile.final_age)
  years = calculate_years_total(profile.date_of_birth, profile.final_age)
  current_year = calculate_age(profile.date_of_birth)

  sum_string = ""

  for topic in topics:
    sum = Sum.objects.filter(topic=topic, user_id=user_id).last()
    if sum is not None:
      sum_string += f"<b>{topic.name}</b>: {sum.content}<br><br>"

  sum_string = mark_safe(sum_string)

  context = {
      'user': user,
      'profile': profile,
      'life_percentage': life_percentage,
      'years': years,
      'topics': topics,
      'current_year': current_year,
      'sum_string': sum_string
  }

  return context


def prepare_existing_conversation_context(user_id, topic_id,
                                          conversation_session_id):

  user = User.objects.get(id=user_id)

  conversation_session = Conversation_Session.objects.filter(
      id=conversation_session_id).first()
  if not conversation_session or conversation_session.user.id != user_id:
    return None

  topic = Topic.objects.get(id=topic_id)

  conversation_session = Conversation_Session.objects.create(user_id=user_id,
                                                             topic=topic)
  print(conversation_session)

  if conversation_session is None:
    return None

  conversations = Conversation.objects.filter(
      conversation_session_id=conversation_session_id).order_by('date_created')
  # update chats available
  Profile.objects.filter(user_id=user_id).update(
      chats_available=F('chats_available') - 1)

  # Get current week
  current_week = Week.objects.filter(date_start__lte=timezone.now(),
                                     date_end__gte=timezone.now()).first()

  conversations_array = []
  for conversation in conversations[1:]:

    date_created = conversation.date_created.strftime('%Y-%m-%d %H:%M:%S')
    conversations_array.append({
        'id': conversation.id,
        'sender': conversation.sender,
        'content': conversation.content,
        'date_created': date_created,
        'date_created_formatted': date_created,
    })

  conversations_json = json.dumps(conversations_array)

  context = {
      'topic_name': topic.name,
      'conversation_session_id': conversation_session_id,
      'conversations': mark_safe(conversations_json),
  }

  return context

  # Query for topics with prefetched weekis


def get_year(year, user_id):

  topics = Topic.objects.filter(user=user_id)
  weeks = Week.objects.filter(year__value=year).prefetch_related(
      Prefetch('weeki_set',
               queryset=Weeki.objects.filter(user_id=user_id),
               to_attr='user_weekis'))
  response = {}
  current_date = date.today()

  profile = Profile.objects.get(user_id=user_id)
  date_of_birth = profile.date_of_birth

  for week in weeks:
    week_value = str(week.value)
    if week_value not in response:
      response[week_value] = {}

    color_array = [
        topic.color for topic in topics
        if any(w for w in week.user_weekis if w.topic_id == topic.id)
    ]
    response[week_value]['week_colors'] = color_array
    response[week_value]['start_date'] = week.date_start.strftime(
        '%-d. %-m.') if week.date_start else None
    response[week_value]['end_date'] = week.date_end.strftime(
        '%-d. %-m.') if week.date_end else None

    print(f"Week {week_value}: start={week.date_start}, end={week.date_end}"
          )  # Debug print

    if week.date_start and week.date_end:
      if week.date_start <= current_date <= week.date_end:
        response[week_value]['current'] = True
        print(f"Week {week_value} is current")  # Debug print
      elif week.date_end < date_of_birth:
        response[week_value]['future'] = True
        print(f"Week {week_value} is future")  # Debug print
      elif week.date_end < current_date:
        response[week_value]['past'] = True
        print(f"Week {week_value} is past")  # Debug print
      else:
        print(f"Week {week_value} is future")  # Debug print

  return response


def get_week_full(week_id, user_id):
  profile = Profile.objects.get(user_id=user_id)
  sorting_descending = profile.sorting_descending
  date_ordering = '-date_created' if sorting_descending else 'date_created'

  original_notes = Original_Note.objects.filter(
      user_id=user_id, week__id=week_id).order_by(date_ordering)

  # Group notes by date
  notes_by_date = defaultdict(list)
  for note in original_notes:
    date_created = note.date_created.date()
    notes_by_date[date_created].append({
        'id': note.id,
        'content': note.content,
        'date_created': note.date_created,
    })

  # Sort notes within each date
  for date, notes in notes_by_date.items():
    notes.sort(key=lambda x: x['date_created'], reverse=sorting_descending)

  # Create the result list with sorted dates
  result = []
  sorted_dates = sorted(notes_by_date.items(),
                        key=lambda x: x[0],
                        reverse=sorting_descending)
  for date, notes in sorted_dates:
    date_data = {'date': date.strftime('%A, %-d. %-m. %Y'), 'notes': notes}
    result.append(date_data)

  return result


def get_week(pagination, page, filter=None):
  weekis = paginate_model(Weeki, pagination, page, filter)

  # Group weekis by date
  weekis_by_date = defaultdict(list)
  for weeki in weekis:
    date_created = timezone.localtime(weeki.date_created).date()
    weekis_by_date[date_created].append({
        'id':
        weeki.id,
        'content':
        weeki.content,
        'favorite':
        weeki.favorite,
        'date_created':
        timezone.localtime(weeki.date_created),
        'color':
        weeki.topic.color if weeki.topic else 'black'
    })

  # Sort weekis and create final structure
  result = []
  # sorted_dates = sorted(weekis_by_date.items(),
  #                       key=lambda x: x[0])

  for date, weekis in weekis_by_date:
    weekis.sort(key=lambda x: x['date_created'])
    date_data = {'date': date.strftime('%A, %-d. %-m. %Y'), 'weekis': weekis}
    result.append(date_data)

  return result


# Create the result list


def get_week_topics(week_id, user_id):
  profile = Profile.objects.get(user_id=user_id)
  sorting_descending = profile.sorting_descending
  ordering = '-date_created' if sorting_descending else 'date_created'

  # Get weekis for the specified week and user, sorted by date_created
  weekis = Weeki.objects.filter(user_id=user_id).order_by(ordering)

  # Get topics with prefetched weekis, sorted by the user's preference
  topics_ordering = '-ordering' if sorting_descending else 'ordering'
  topics_with_weekis = Topic.objects.filter(
      user_id=user_id).order_by(topics_ordering).prefetch_related(
          Prefetch('weeki_set', queryset=weekis, to_attr='filtered_weekis'))

  result = []
  for topic in topics_with_weekis:
    # Sort weekis within each topic based on the user's preference
    sorted_weekis = sorted(topic.filtered_weekis,
                           key=lambda w: w.date_created,
                           reverse=sorting_descending)

    topic_data = {
        'id':
        topic.id,
        'color':
        topic.color,
        'name':
        topic.name,
        'weekis': [
            {
                'id': weeki.id,
                'favorite': weeki.favorite,
                'content': weeki.content,
                'date_created': weeki.date_created,
                # Add other weeki fields as needed
            } for weeki in sorted_weekis
        ]
    }
    result.append(topic_data)

  return result


# Topics


def get_user_active_topics(user_id):

  topics = Topic.objects.filter(user_id=user_id,
                                active=True).order_by('ordering')

  return topics


def get_user_inactive_topics(user_id):

  topics = Topic.objects.filter(user_id=user_id,
                                active=False).order_by('-date_created')

  return topics


def get_object_or_error(model, id):
  try:
    return model.objects.get(id=id)
  except model.DoesNotExist:
    return Response({'error': True, 'message': 'Not all data'})


def week_filter(year):
  return Week.objects.filter(year__value=year)


def topic_filter(userId):
  return Topic.objects.filter(user_id=userId, active=True)


def get_current_week_id():
  current_date = timezone.now().date()
  week = Week.objects.filter(date_start__lte=current_date,
                             date_end__gte=current_date).first()
  weekID = week.id
  return weekID


def get_topic(pagination, page, filter):
  weekis = paginate_model(Weeki, pagination, page, filter)
  weekis_by_date = defaultdict(list)

  for weeki in weekis:
    date_created = timezone.localtime(weeki.date_created).date()
    weekis_by_date[date_created].append({
        'id':
        weeki.id,
        'content':
        weeki.content,
        'favorite':
        weeki.favorite,
        'date_created':
        timezone.localtime(weeki.date_created),
        'color':
        'black'  # Since topics don't have colors in original
    })

  result = []
  for date, weekis in weekis_by_date.items():
    weekis.sort(key=lambda x: x['date_created'])
    result.extend(weekis)

  return result
