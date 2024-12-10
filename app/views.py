from api.services import calculate_life_percentage, calculate_years_total, calculate_age, get_user_active_topics, get_user_inactive_topics, prepare_first_conversation_context, chat_with_nurmo, prepare_existing_conversation_context, get_build_context
from django.db import transaction

import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta, datetime

from django.utils import timezone
from django.core.paginator import Paginator
from asgiref.sync import sync_to_async
import os
import asyncio
import logging

from django.core.mail import send_mail
from api.utilities.midjourney import download_image_from_url_and_save, midjourney_send_and_get_job_id, midjourney_main, midjourney_receive_image
from api.utilities.anthropic import AnthropicAPIUtility

from django.contrib.auth import update_session_auth_hash

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from deepgram import Deepgram
from django.conf import settings

from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views import View
import anthropic
from django.urls import reverse

from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import update_session_auth_hash

import json

from .models import Original_Note, Weeki, Profile, Week, Year, Topic, User, Translation, Conversation, Prompt, Conversation_Session, Sum
from django.contrib.auth import login, logout
from django.http import HttpResponse
from django.template.loader import get_template
# from xhtml2pdf import pisa
from .forms import NewWeekiForm, EditWeekiForm, ProfileFormLater, UserSettingsForm, TopicForm, PasswordChangeForm
from jinja2 import Template
from collections import defaultdict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from api.utilities.utils import log_error
from api.utilities.regex import clean_content
from django.utils.decorators import method_decorator

from datetime import datetime

from api.services import get_year, get_week_topics, get_week_full, fetch_years, year_filter, topic_filter, week_filter

import json
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def index(request):
  return redirect('app:week')


def rec(request):
  return render(request, 'x.html')


class NewWeekiView(View):
  template_name = 'weeki/new_weeki.html'

  def get(self, request, weekID=None):

    if weekID:
      week = get_object_or_404(Week, pk=weekID)
    else:
      current_date = timezone.now().date()
      week = Week.objects.filter(date_start__lte=current_date,
                                 date_end__gte=current_date).first()
      weekID = week.id

    # Initialize the form with an empty week_id
    form = NewWeekiForm(initial={'week_id': weekID})

    context = {'form': form, 'week': week}
    return render(request, self.template_name, context)

  def post(self, request, weekID=None):
    form = NewWeekiForm(request.POST)
    if form.is_valid():
      content = request.POST.get('content', '')

      content = clean_content(content)

      week_id = form.cleaned_data['week_id']

      try:
        api_utility = AnthropicAPIUtility()

        topics = Topic.objects.filter(user_id=request.user.id, active=True)

        topic_strings = ""
        for topic in topics:
          topic_strings += f"{topic.id} - {topic.name} - {topic.description}|"

        placeholders = {
            "content":
            content,
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

        response = api_utility.make_api_call("weeki_disect_and_categorize_2",
                                             placeholders)

        week = get_object_or_404(Week, pk=week_id)

        response_json = json.loads(response)

        for block in response_json:
          for topic_id_str, content_stripped in block.items():
            topic_id = int(topic_id_str)
            topic = get_object_or_404(Topic, pk=topic_id)

            content_stripped = content_stripped.strip()

            new_original_note = {
                'user': request.user,
                'content': content,
                'week': week,
            }

            new_weeki = {
                'user': request.user,
                'content': content_stripped,
                'week': week,
                'topic': topic
            }

            print(new_weeki)

            Original_Note.objects.create(**new_original_note)

            Weeki.objects.create(**new_weeki)

        if weekID is None:
          return redirect(reverse('app:week'))
        else:
          return redirect('app:week_with_year_and_week',
                          year=week.year.value,
                          week=week.value)

      except Exception as e:
        error_message = f"Error creating Weeki: {str(e)}"
        log_error(request, error_message, {
            'content': content,
            'week_id': week_id,
        })
        messages.error(request, error_message)

    else:
      print("Form is invalid")
      print(form.errors)

    return render(request, self.template_name, {'form': form})


def get_week_of_year(d):
  return (d - date(d.year, 1, 1)).days // 7 + 1


def memento_mori(request):
  profile = request.profile
  date_of_birth = profile.date_of_birth
  final_age = profile.final_age

  birth_week = get_week_of_year(date_of_birth)
  today = date.today()
  current_week = get_week_of_year(today)

  start_year = date_of_birth.year
  end_year = start_year + final_age
  weeks_per_year = 52

  years_data = []
  for year in range(start_year, end_year + 1):
    year_weeks = []
    for week in range(1, weeks_per_year + 1):
      is_filled = (year > date_of_birth.year or (year == date_of_birth.year and week >= birth_week)) and \
                  (year < today.year or (year == today.year and week <= current_week))

      year_weeks.append({
          'filled': is_filled,
          'last': False,  # We'll set this later
          'label': week if week % 4 == 0 else None
      })

    years_data.append({
        'year': year,
        'weeks': year_weeks,
        'show_label': (year - start_year) % 5 == 0
    })

  # Set the 'last' flag for the last filled week
  last_filled_found = False
  for year_data in reversed(years_data):
    for week in reversed(year_data['weeks']):
      if week['filled']:
        if not last_filled_found:
          week['last'] = True
          last_filled_found = True
        break
    if last_filled_found:
      break

  context = {
      'years_data': years_data,
  }
  return render(request, 'build/memento_mori.html', context)


@method_decorator(login_required, name='dispatch')
class EditWeekiView(View):
  template_name = 'weeki/edit_weeki.html'

  def get(self, request, weeki_id):
    weeki = get_object_or_404(Weeki, pk=weeki_id, user=request.user)

    week = Week.objects.get(pk=weeki.week.pk)

    form = EditWeekiForm(instance=weeki)
    topics = Topic.objects.filter(user_id=request.user.id,
                                  active=True).order_by('ordering')
    context = {'form': form, 'week': week, 'weeki': weeki, 'topics': topics}
    return render(request, self.template_name, context)

  @method_decorator(require_POST)
  def post(self, request, weeki_id):
    weeki = get_object_or_404(Weeki, pk=weeki_id, user=request.user)
    action = request.POST.get('action')

    if action == 'delete':
      try:
        weeki.delete()
        return JsonResponse({"success": True, "message": f"Success!"})
      except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Error updating Weeki: {str(e)}"
        })

    form = EditWeekiForm(request.POST, instance=weeki)

    # Print received data for debugging

    if form.is_valid():
      try:
        weeki = form.save(commit=False)
        cleaned_content = clean_content(form.cleaned_data['content'])
        weeki.content = cleaned_content
        weeki.save()
        return JsonResponse({"success": True, "message": "Success"})
      except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Error updating Weeki: {str(e)}"
        })
    else:
      errors = {field: str(error) for field, error in form.errors.items()}
      return JsonResponse({"success": False, "errors": errors})


def year_view(request, year=None):

  if year == None:
    year = datetime.now().year

  profile = request.profile

  selected_year = Year.objects.get(value=year)

  selected_year.age = year - profile.date_of_birth.year

  current_year = datetime.now().year

  user_id = request.user.id

  data = get_year(selected_year.value, user_id)

  profile = request.profile
  year_of_birth = profile.date_of_birth.year
  final_age = profile.final_age

  years = fetch_current_years(year_of_birth)

  context = {
      'years': years,
      'selected_year': selected_year,
      'data': json.dumps(data),
      'current_year': current_year,
  }

  return render(request, 'year/year_list.html', context)


def week_view(request, year=None, week=None):
  current_date = timezone.now().date()

  t_week = Translation.get_translation("week", request.language_code)

  if year is None or week is None:
    weekObject = Week.objects.filter(date_start__lte=current_date,
                                     date_end__gte=current_date).first()
    if weekObject is None:
      return redirect('app:week')
    year = weekObject.year.value
    week = weekObject.value
  else:
    weekObject = get_object_or_404(Week, value=week, year__value=year)

    # Check if the requested week is in the future
    if weekObject.date_start > current_date:
      # If it's in the future, redirect to the current week
      return redirect('app:week')

  profile = request.profile
  sorting = profile.sorting_type
  if sorting == 'topics':
    labeled_weekis = get_week_topics(weekObject.id, request.user.id)
  elif sorting == 'days':
    labeled_weekis = get_week_days(weekObject.id, request.user.id)
  else:
    labeled_weekis = get_week_full(weekObject.id, request.user.id)

  weeks = Week.objects.filter(year__value=weekObject.year.value)

  if weekObject.year.value == current_date.year:
    weeks = list(weeks.filter(date_start__lte=current_date))[::-1]

  context = {
      'week': weekObject,
      'weeks': weeks,
      'year': year,
      't_week': t_week,
      'selected_week': weekObject,
      'labeled_weekis': labeled_weekis,
      'sorting': sorting,
      'sorting_types': ['topics', 'days', 'full'],
  }

  return render(request, 'week/week_list.html', context)


# return render(request, "week/week_list.html", context)


@require_http_methods(["DELETE"])
def weeki_delete_view(request, weeki_id):
  """
    View to handle deletion of a Weeki object.

    Args:
    - request: The HTTP request object
    - weeki_id: The ID of the Weeki to be deleted

    Returns:
    - JsonResponse with success status and message
    """
  try:
    # Retrieve the Weeki object or return 404 if not found
    weeki = get_object_or_404(Weeki, id=weeki_id)

    # Delete the Weeki object
    weeki.delete()

    # Return a success response
    return JsonResponse({
        "success":
        True,
        "message":
        f"Weeki with ID {weeki_id} has been successfully deleted."
    })
  except Exception as e:
    # If any error occurs during deletion, return an error response
    return JsonResponse({"success": False, "message": str(e)}, status=500)


def build_view(request):

  user = request.user
  user_id = user.id
  context = get_build_context(user_id)

  return render(request, 'build/build.html', context)

  # def download_file(request):

  #   user = request.user
  #   user_id = user.id
  #   url = "https://cdnb.ttapi.io/20240811/yaorkg3ltiis0712.png"
  #   download_image_from_url_and_save(url, user_id)

  # def midjourney(request):
  #   midjourney_send_and_get_job_id("logo for app called weeki")

  # def midjourney_fetch(request):
  #   job_id = "376a5068-5ac5-454b-b3a7-ed9bc259b4f4"
  #   midjourney_receive_image(job_id)


def edit_profile(request):
  user = request.user
  profile = request.user.profile

  if request.method == 'POST':
    form = ProfileFormLater(request.POST, instance=profile)
    new_username = request.POST.get('username')

    if form.is_valid():
      try:
        with transaction.atomic():
          # Save the profile
          updated_profile = form.save(commit=False)
          updated_profile.user = user  # Ensure the user is set
          updated_profile.save()

          # Handle username change
          if new_username and new_username != user.username:
            if User.objects.filter(username=new_username).exists():
              messages.error(request, 'This username is already taken.')
            else:
              user.username = new_username
              user.save()
              messages.success(request,
                               'Your username was successfully updated!')

          messages.success(request, 'Your profile was successfully updated!')

          # Debug information
          print(f"Updated profile: {updated_profile.__dict__}")
          print(f"Form cleaned data: {form.cleaned_data}")

      except Exception as e:
        messages.error(
            request, f'An error occurred while saving your profile: {str(e)}')
        print(f"Error saving profile: {str(e)}")

      return redirect('app:edit_profile')
    else:
      messages.error(request, 'Please correct the errors below.')
      print(f"Form errors: {form.errors}")
  else:
    form = ProfileFormLater(instance=profile)

  return render(request, 'build/edit_profile.html', {
      'profile_form': form,
  })


@require_POST
def change_password(request):
  form = PasswordChangeForm(request.user, request.POST)
  if form.is_valid():
    user = form.save()
    update_session_auth_hash(request,
                             user)  # Important to keep the user logged in
    messages.success(request, 'Your password was successfully updated!')
  else:
    messages.error(request, 'Please correct the errors below.')
  return redirect('edit_profile')


@require_POST
def change_password(request):
  form = PasswordChangeForm(request.user, request.POST)
  if form.is_valid():
    user = form.save()
    update_session_auth_hash(request,
                             user)  # Important to keep the user logged in
    messages.success(request, 'Your password was successfully updated!')
  else:
    messages.error(request, 'Please correct the errors below.')
  return redirect('edit_profile')


# class Topics(FormView):
#   template_name = 'build/topics.html'
#   form_class = TopicForm

#   def get_context_data(self, **kwargs):
#       context = super().get_context_data(**kwargs)
#       context['active_topics'] = Topic.objects.filter(user=self.request.user, active=True).order_by('ordering')
#       context['inactive_topics'] = Topic.objects.filter(user=self.request.user, active=False).order_by('ordering')
#       return context

#   def form_valid(self, form):
#       action = self.request.POST.get('action')
#       if action == 'update':
#           return self.update_topic(form)
#       elif action == 'delete':
#           return self.delete_topic()
#       elif action == 'reorder':
#           return self.reorder_topics()
#       elif action == 'get':
#           return self.get_topic()
#       return JsonResponse({'status': 'error', 'message': 'Invalid action'})

#   def update_topic(self, form):
#       topic = form.save(commit=False)
#       topic.user = self.request.user
#       topic.save()
#       return JsonResponse({'status': 'success', 'topic': self.topic_to_dict(topic)})

#   def delete_topic(self):
#       topic_id = self.request.POST.get('id')
#       topic = get_object_or_404(Topic, id=topic_id, user=self.request.user)
#       topic.delete()
#       return JsonResponse({'status': 'success'})

#   def reorder_topics(self):
#       topic_order = self.request.POST.getlist('topic_order[]')
#       for index, topic_id in enumerate(topic_order):
#           topic = get_object_or_404(Topic, id=topic_id, user=self.request.user)
#           topic.ordering = index
#           topic.save()
#       return JsonResponse({'status': 'success'})

#   def get_topic(self):
#       topic_id = self.request.POST.get('id')
#       topic = get_object_or_404(Topic, id=topic_id, user=self.request.user)
#       return JsonResponse({'status': 'success', 'topic': self.topic_to_dict(topic)})

#   def topic_to_dict(self, topic):
#       return {
#           'id': topic.id,
#           'name': topic.name,
#           'color': topic.color,
#           'description': topic.description,
#           'active': topic.active
#       }


def topics_view(request):

  user = request.user

  user_id = user.id

  active_topics = get_user_active_topics(user_id)
  inactive_categores = get_user_inactive_topics(user_id)

  context = {
      "active_topics": active_topics,
      "inactive_categores": inactive_categores
  }

  return render(request, 'build/topics.html', context)


def update_topic_order(request):
  if request.method == 'POST':
    topic_order = request.POST.getlist('topic_order[]')
    for index, topic_id in enumerate(topic_order):
      topic = Topic.objects.get(id=topic_id, user=request.user)
      topic.ordering = index
      topic.save()
    return JsonResponse({'status': 'success'})
  return JsonResponse({'status': 'error'}, status=400)


def toggle_topic_active(request, topic_id):
  topic = Topic.objects.get(id=topic_id, user=request.user)
  active_count = Topic.objects.filter(user=request.user, active=True).count()

  if not topic.active and active_count >= 6:
    return JsonResponse(
        {
            'status': 'error',
            'message': 'Maximum 6 active topics allowed'
        },
        status=400)

  topic.active = not topic.active
  topic.save()
  return JsonResponse({'status': 'success', 'active': topic.active})


def delete_topic(request, topic_id):
  topic = Topic.objects.get(id=topic_id, user=request.user)
  topic.delete()
  return JsonResponse({'status': 'success'})


@method_decorator(ensure_csrf_cookie, name='dispatch')
class TopicEdit(View):

  def get(self, request, topic_id=None):
    user = request.user
    profile = request.profile
    if topic_id:
      topic = get_object_or_404(Topic, id=topic_id, user=user)
      form = TopicForm(instance=topic, user=user)
    else:
      form = TopicForm(user=user)

    context = topic_view_initial(user.id, topic_id, profile.topic_view)
    context['form'] = form
    return render(request, 'build/topic_list.html', context)

  def post(self, request, topic_id=None):
    user = request.user
    user_id = user.id

    # Check if this is a request to load more topics
    if 'offset' in request.POST:
      # Existing code for loading more topics
      offset = int(request.POST.get('offset', 0))
      context = topic_view_more(user_id, topic_id, offset)
      return JsonResponse(context)
    else:
      # Handle form submission
      topic = Topic.objects.get(id=topic_id, user_id=user_id)
      form = TopicForm(request.POST, instance=topic, user=user)
      if form.is_valid():
        form.save()
        return JsonResponse({'success': True})
      else:
        return JsonResponse({'success': False, 'errors': form.errors})


@method_decorator(ensure_csrf_cookie, name='dispatch')
class MrWeek(View):

  def get(self, request, topic="0", conversation_session_id="0"):
    user = request.user
    if topic == "0":
      topic = Topic.objects.filter(user=user, active=True).first()
    else:
      topic = Topic.objects.filter(user=user, id=topic).first()

    if not topic:
      return JsonResponse({"error": "Topic not found"}, status=404)

    if conversation_session_id == "0":
      context = prepare_first_conversation_context(user.id, topic.id)
    else:
      context = prepare_existing_conversation_context(user.id, topic.id,
                                                      conversation_session_id)

    print(context)

    return render(request, 'build/mr_week.html', context)

  def post(self, request):
    data = json.loads(request.body)

    user_message = data.get('message', '')
    conversation_session_id = data.get('conversation_session_id', '')

    conversation_history = Conversation.objects.filter(
        conversation_session_id=conversation_session_id)

    conversation_array = []
    for conversation in conversation_history:
      conversation_object = {
          "role": conversation.sender,
          "content": conversation.content
      }

      conversation_array.append(conversation_object)

    nurmo_response = chat_with_nurmo(conversation_session_id,
                                     conversation_array, user_message, False)

    # Save AI response to database
    if not isinstance(nurmo_response, dict):
      nurmo_response = {"message": str(nurmo_response)}

    return JsonResponse(nurmo_response)


def payment_view(request):
  user = request.user
  profile = request.profile


async def process_image_generation(user_id, prompt):
  image_path = os.path.join(settings.MEDIA_ROOT, "media/profile_images",
                            f"{user_id}.png")
  if os.path.exists(image_path):
    os.remove(image_path)
  success = await asyncio.to_thread(midjourney_main, prompt, user_id)
  return success


async def process_user(profile, api_utility):
  user = await sync_to_async(User.objects.get)(id=profile.user_id)
  topics = await sync_to_async(list)(Topic.objects.filter(user_id=user.id,
                                                          active=True))
  print("ahoj")
  complet_weekis_string = ""

  for topic in topics:
    try:
      today = date.today()
      current_week = await sync_to_async(
          Week.objects.filter(date_start__lte=timezone.now(),
                              date_end__gte=timezone.now()).first)()

      weekis = await sync_to_async(list)(Weeki.objects.filter(
          topic=topic,
          date_created__gte=timezone.now() - timedelta(days=7))[:100])

      weekis_string = "|".join(weeki.content for weeki in weekis)
      complet_weekis_string += weekis_string + "|"

      if weekis_string:
        placeholders = {"content": weekis_string}
        summary = await sync_to_async(api_utility.make_api_call
                                      )("summarize_topic_week", placeholders)
        await sync_to_async(Sum.objects.create)(topic=topic,
                                                content=summary,
                                                user=user,
                                                week=current_week)
    except Exception as e:
      print(f"Error processing topic {topic.id} for user {user.id}: {str(e)}")

  if complet_weekis_string:
    placeholders = {"content": complet_weekis_string.strip("|")}
    image_prompt = await sync_to_async(api_utility.make_api_call
                                       )("midjourney_prompt_creator",
                                         placeholders)
    return {'user_id': user.id, 'prompt': image_prompt}

  return None


@csrf_exempt
async def cron_job(request):
  current_time = timezone.localtime()
  hour_number = current_time.hour
  day_number = current_time.weekday() + 1

  profiles = await sync_to_async(list)(Profile.objects.filter(
      reminder_day=day_number, reminder_hour=hour_number))
  print(hour_number)
  print(day_number)

  api_utility = AnthropicAPIUtility()
  users_data = []

  for profile in profiles:
    try:
      result = await process_user(profile, api_utility)
      if result:
        users_data.append(result)
    except Exception as e:
      print(f"Error processing user {profile.user_id}: {str(e)}")

  # Reset availability for Mr. Week
  try:
    await sync_to_async(
        Profile.objects.filter(id__in=[p.id for p in profiles]).update
    )(chats_available=100, chat_sessions_available=10)
  except Exception as e:
    print(f"Error resetting availability: {str(e)}")

  # Here you would implement the mail sendout

  return JsonResponse({
      'status': 'success',
      'users_processed': len(users_data)
  })


# async def cron_job(request):

#   user_id = request.user.id
#   current_time = timezone.localtime()
#   hour_number = current_time.hour
#   day_number = current_time.weekday() + 1

#   profiles = await sync_to_async(list)(Profile.objects.filter(
#       reminder_day=day_number, reminder_hour=hour_number))

#   complet_weekis_string = ""

#   api_utility = AnthropicAPIUtility()

#   async def process_image_generation(user_id, prompt):
#     image_path = os.path.join(settings.MEDIA_ROOT, "media/profile_images",
#                               f"{user_id}.png")
#     if os.path.exists(image_path):
#       os.remove(image_path)
#     success = await asyncio.to_thread(midjourney_main, prompt, user_id)
#     return success

#   async def process_user(profile):
#     user = profile.user
#     user_id = user.id

#     topics = await sync_to_async(list)(Topic.objects.filter(user_id=user_id,
#                                                             active=True))

#     # create summary and save
#     complet_weekis_string = ""
#     for topic in topics:
#       try:

#         today = date.today()
#         current_week = get_week_of_year(today)

#         weekis = await sync_to_async(list)(Weeki.objects.filter(
#             topic=topic,
#             active=True,
#         ))

#         weekis_string = ""
#         for weeki in weekis:
#           weekis_string += f"{weeki.content} |"
#           complet_weekis_string += f"{weeki.content} |"

#         if len(weekis_string) > 0:

#           weekis_string = weekis_string.strip("|")

#           placeholders = {
#               "content": weekis_string,
#           }

#           summary = await sync_to_async(api_utility.make_api_call
#                                         )("summarize_topic_week", placeholders)

#           await sync_to_async(Sum.objects.create)(topic=topic,
#                                                   content=summary,
#                                                   user=user,
#                                                   week=current_week)

#       except Exception as e:
#         print(
#             f"Error creating Summary for user {user_id}, topic {topic.id}: {str(e)}"
#         )

#     if len(complet_weekis_string) > 0:
#       # create image prompt
#       placeholders = {
#           "content": complet_weekis_string,
#       }

#       image_prompt = api_utility.make_api_call("midjourney_prompt_creator",
#                                                placeholders)
#       return {'user_id': user_id, 'prompt': image_prompt}

#   users_data = await asyncio.gather(
#       *[process_user(profile) for profile in profiles])
#   # Process images in batches of 9

#   # results = []
#   # for i in range(0, len(users_data), 9):
#   #   batch = users_data[i:i + 9]
#   #   batch_results = await asyncio.gather(*[
#   #       process_image_generation(data['user_id'], data['prompt'])
#   #       for data in batch if data is not None
#   #   ])
#   #   results.extend(batch_results)
#   # # Process results
#   # for user_data, success in zip(users_data, results):
#   #   if success:
#   #     if user_data is not None:
#   #       print(f"Image generated successfully for user {user_data['user_id']}")
#   #     else:
#   #       print(f"Image generation failed for user {user_data}")

#   # Reset availability for Mr. Week
#   await sync_to_async(
#       Profile.objects.filter(id__in=[p.id for p in profiles]).update
#   )(chats_available=100, chat_sessions_available=10)

#   # mail sendout
#   return JsonResponse({'status': 'success'})

# def mr_week_view(request, topic="0"):

#   user = request.user

#   if topic == 0:
#     topic = Topic.objects.filter(user=user).fist()
#   else:
#     topic = Topic.objects.filter(user=user, id=topic).fist()

#   topic = request.GET.get('topic', '')
#   print(topic)

#   return render(request, 'extra/mr_week.html')

# @csrf_exempt
# def send_chat_message(request):
#   if request.method == 'POST':
#     data = json.loads(request.body)
#     user_message = data.get('message', '')
#     topic_id = data.get('topic_id', '')

#     topic = Topic.objects.get(id=topic_id)

#     weekis = Weeki.objects.filter(topic=topic)

#     weekis_string = ''
#     for weeki in weekis:
#       weekis_string += weeki.content

#     conversations = Conversation.objects.filter(topic=topic)

#     conversations_string = ''
#     for conversation in conversations:
#       conversations_string += conversation.content

#     topic_description = topic.description

#     notes = data.get('notes', '')
#     conversations = data.get('conversations', '')

#     api_utility = AnthropicAPIUtility()

#     placeholders = {
#         "content": user_message,
#         "topic_id": topic_id,
#         "topic_description": topic_description,
#         "notes": weekis_string,
#         "conversations": conversations_string,
#     }

#     response = api_utility.make_api_call("mr_week", placeholders,
#                                          "claude-3-5-sonnet-20240620")

#     return JsonResponse({'message': response})

#   return JsonResponse({'error': 'Invalid request method'}, status=400)

# def weeki_pdf(request):
#   return render(request, 'weeki_pdf.html')
# weekis = Weeki.objects.all().order_by('-date_created')

# template_path = 'pdf_convert/pdf_memo_overview.html'
# context = {'weekis': weekis}
# # Create a Django response object, and specify content_type as pdf
# response = HttpResponse(content_type='application/pdf')
# # add name of user
# response['Content-Disposition'] = 'filename="weeki_overview.pdf"'
# # find the template and render it.
# template = get_template(template_path)
# html = template.render(context)

# # create a pdf
# pisa_status = pisa.CreatePDF(html, dest=response)
# # if error then show some funny view
# if pisa_status.err:
#   return HttpResponse('We had some errors <pre>' + html + '</pre>')
# return response
