from django.db.models import Prefetch
from app.models import Category, Weeki, Week, Profile
from .serializers import CategorySerializer
from django.utils import timezone
from datetime import date


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


def fetch_years(year_of_birth, final_age):
  return list(
      reversed(range(int(year_of_birth), int(year_of_birth + final_age + 1))))


def fetch_current_years(year_of_birth):
  current_year = int(date.today().year)
  years = list(reversed(range(int(year_of_birth), current_year + 1)))
  max_index = len(years) - 1

  return [{
      'value': year,
      'index': max_index - i
  } for i, year in enumerate(years)]


def get_year(year, user_id):
  categories = Category.objects.all()
  weeks = Week.objects.filter(year__value=year).prefetch_related(
      Prefetch('weeki_set',
               queryset=Weeki.objects.filter(user_id=user_id),
               to_attr='user_weekis'))
  response = {}
  current_date = date.today()
  print(f"Current date: {current_date}")  # Debug print

  profile = Profile.objects.get(user_id=user_id)
  date_of_birth = profile.date_of_birth

  for week in weeks:
    week_value = str(week.value)
    if week_value not in response:
      response[week_value] = {}

    color_array = [
        category.default_color for category in categories
        if any(w for w in week.user_weekis if w.category_id == category.id)
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


def get_week(week_id, user_id):
  weekis = Weeki.objects.filter(user_id=user_id,
                                week__id=week_id).order_by('-date_created')

  categories_with_weekis = Category.objects.prefetch_related(
      Prefetch('weeki_set', queryset=weekis,
               to_attr='filtered_weekis')).order_by('-id')

  result = []
  for category in categories_with_weekis:
    category_data = {
        'id':
        category.id,
        'default_color':
        category.default_color,
        'name':
        category.name,
        'weekis': [
            {
                'id': weeki.id,
                'content': weeki.content,
                'date_created': weeki.date_created,
                # Add other weeki fields as needed
            } for weeki in category.filtered_weekis
        ]
    }
    result.append(category_data)

  return result

  # Get user_id (use the authenticated user's ID if not provided)
  # Query for weekis
  # weekis = Weeki.objects.filter(user_id=user_id, week__value=week)

  # # Query for categories with prefetched weekis
  # categories_with_weekis = Category.objects.prefetch_related(
  #     Prefetch('weeki_set', queryset=weekis, to_attr='filtered_weekis')).all()

  # print(categories_with_weekis)

  # return categories_with_weekis
