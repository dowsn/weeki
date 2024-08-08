from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from django.utils import timezone
from api.ai.anthropic import AnthropicAPIUtility
from api.ai.prompts import prompt_library, PromptTemplate
from api.services import calculate_life_percentage

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

import json
from .utils import log_error
from .models import Weeki, Profile, Week, Year, Category, Translation
from django.contrib.auth import login, logout
from django.http import HttpResponse
from django.template.loader import get_template
# from xhtml2pdf import pisa
from .forms import NewWeekiForm, EditWeekiForm
from jinja2 import Template
from collections import defaultdict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from django.utils.decorators import method_decorator

from datetime import datetime

from api.services import get_year, get_week, fetch_years, fetch_current_years

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
      content = request.POST.get('content', '')  # Get content from POST data
      favorite = request.POST.get('favorite') == 'on'

      # Get favorite from POST data
      week_id = form.cleaned_data['week_id']

      try:
        api_utility = AnthropicAPIUtility()

        placeholders = {
            "content": content,
        }

        response = api_utility.make_api_call("weeki_disect_and_categorize",
                                             placeholders)

        response_messages = response.split('|#|')

        week = get_object_or_404(Week, pk=week_id)

        for response_message in response_messages:
          response_stripped = response_message.strip()

          if response_stripped:
            category_id = int(response_stripped.strip()[0])
            category = get_object_or_404(Category, pk=category_id)
            content_stripped = response_stripped.strip()[1:]

            new_weeki = {
                'user': request.user,
                'content': content_stripped,
                'week': week,
                'favorite': favorite,
                'category': category
            }

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
  return render(request, 'extra/memento_mori.html', context)


@method_decorator(login_required, name='dispatch')
class EditWeekiView(View):
  template_name = 'weeki/edit_weeki.html'

  def get(self, request, weeki_id):
      weeki = get_object_or_404(Weeki, pk=weeki_id, user=request.user)
      form = EditWeekiForm(instance=weeki)
      categories = Category.objects.all().order_by('-id')
      context = {'form': form, 'weeki': weeki, 'categories': categories}
      return render(request, self.template_name, context)

  @method_decorator(require_POST)
  def post(self, request, weeki_id):
      weeki = get_object_or_404(Weeki, pk=weeki_id, user=request.user)
      action = request.POST.get('action')

      if action == 'delete':
          weeki.delete()
          return JsonResponse({"success": True, "message": "Weeki deleted successfully."})

      form = EditWeekiForm(request.POST, instance=weeki)

      # Print received data for debugging
      print("Received POST data:", request.POST)

      if form.is_valid():
          try:
              updated_weeki = form.save()
              return JsonResponse({
                  "success": True,
                  "message": "Weeki updated successfully.",
                  "redirect_url": reverse('app:week_with_year_and_week', kwargs={
                      'year': updated_weeki.week.year.value,
                      'week': updated_weeki.week.value
                  })
              })
          except Exception as e:
              return JsonResponse({"success": False, "message": f"Error updating Weeki: {str(e)}"})
      else:
          errors = {field: str(error) for field, error in form.errors.items()}
          return JsonResponse({"success": False, "errors": errors})


def year_view(request, year=None):

  if year:
    selected_year = year
  else:
    selected_year = datetime.now().year

  current_year = datetime.now().year

  user_id = request.user.id

  data = get_year(selected_year, user_id)

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

  categories_with_weekis = get_week(weekObject.id, request.user.id)

  weeks = Week.objects.filter(year__value=weekObject.year.value)

  if weekObject.year.value == current_date.year:
    weeks = list(weeks.filter(date_start__lte=current_date))[::-1]

  selected_week = weekObject.id
  context = {
      'week': weekObject,
      'weeks': weeks,
      'year': year,
      't_week': t_week,
      'selected_week': selected_week,
      'categories_with_weekis': categories_with_weekis
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


def weeki_edit_view(request, id):

  weeki = get_object_or_404(Weeki, id=id)

  postButtonText = "Save"

  week = weeki.week.value

  initial_data = {
      "content": "",
      "category": 1,
      "user_id": request.user.id,
      "week": week
  }

  form = RawWeekiForm(request.POST or None, initial=initial_data, instance=obj)

  if request.method == "POST":
    if form.is_valid():
      Weeki.objects.create(**form.cleaned_data)
      return redirect('../')  # Redirect to the list view after saving

  elif request.method == "DELETE":
    obj.delete()
    return redirect('../')  # Redirect to the list view after deleting

  context = {'form': form, 'postButtonText': postButtonText, 'weeks': weeks}

  return render(request, 'weeki_crud.html', context)


def extra_view(request):

  profile = request.profile
  user = request.user
  life_percentage = calculate_life_percentage(profile.date_of_birth,
                                              profile.final_age)

  context = {
      'user': user,
      'profile': profile,
      'life_percentage': life_percentage,
  }
  return render(request, 'extra/extra.html', context)


def social_view(request):
  return render(request, 'social/social.html')


def app_settings(request):
  profile = request.profile
  user = request.user

  if request.method == 'POST':
    form = ProfileForm(request.POST, request.FILES, instance=profile)
    if form.is_valid():
      form.save()
      return redirect('app:settings')  # Redirect to profile page after saving
  else:
    form = ProfileForm(instance=profile)

    context = {'form': form}
    return render(request, 'extra/app_settings.html', context)


def weeki_pdf(request):
  return render(request, 'weeki_pdf.html')
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
