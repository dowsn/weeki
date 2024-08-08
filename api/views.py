from django.http import JsonResponse
from app.models import Weeki, Week, Profile, Category, User, Year
from app.utils import *
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

from django.db.models import Prefetch
from .utils import parse_request_data, validate_required_fields, safe_int_conversion, handle_exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import WeekiSerializer
from .serializers import WeekSerializer
from .serializers import YearSerializer
from .serializers import CategorySerializer


class CategoriesWithWeekis(APIView):
  authentication_classes = [JWTAuthentication]
  permission_classes = [IsAuthenticated]

  def post(self, request):
    year = request.data.get('year')
    week = request.data.get('week')

    try:
      year = int(year)
      week = int(week)
    except (ValueError, TypeError):
      return Response({"error": "Year and week must be valid integers"},
                      status=status.HTTP_400_BAD_REQUEST)

    categories_data = "ahoj"
    return Response({"categories": categories_data})


# @api_view(['POST'])
# def get_token(request):
#     # Validate the user's credentials (e.g., using session-based authentication)
#     user = request.user
#     if user.is_authenticated:
#         # Generate the JWT access token
#         refresh = RefreshToken.for_user(user)
#         return Response({
#             'access': str(refresh.access_token),
#             'refresh': str(refresh)
#         })
#     else:
#         return Response({'error': 'Invalid credentials'}, status=401)


class NoteListView(APIView):

  def get(self, request):
    notes = Note.objects.all()
    serializer = NoteSerializer(notes, many=True)
    return Response(serializer.data)


class getCategoriesWithWeekisX(APIView):
  authentication_classes = [SessionAuthentication, JWTAuthentication]
  permission_classes = [IsAuthenticated]

  def post(self, request):
    # Get data from request
    data = request.data

    # Validate required fields
    required_fields = ['year', 'week']
    for field in required_fields:
      if field not in data:
        return Response({"error": f"Missing required field: {field}"},
                        status=status.HTTP_400_BAD_REQUEST)

    # Convert and validate year and week
    try:
      year = int(data['year'])
      week = int(data['week'])
    except ValueError:
      return Response({"error": "Year and week must be integers"},
                      status=status.HTTP_400_BAD_REQUEST)

    # Get user_id (use the authenticated user's ID if not provided)
    user_id = data.get('user_id', request.user.id)

    # Query for weekis
    weekis = Weeki.objects.filter(user_id=user_id, week__value=week, year=year)

    # Query for categories with prefetched weekis
    categories_with_weekis = Category.objects.prefetch_related(
        Prefetch('weeki_set', queryset=weekis,
                 to_attr='filtered_weekis')).all()

    # Serialize the data
    serializer = CategorySerializer(categories_with_weekis,
                                    many=True,
                                    context={'request': request})

    return Response(serializer.data)


class NoteDetailView(APIView):

  def get(self, request, pk):
    note = Note.objects.get(pk=pk)
    serializer = NoteSerializer(note)
    return Response(serializer.data)


class getYear2(APIView):
  authentication_classes = [SessionAuthentication, JWTAuthentication]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    return Response({
        "message": "This is a protected endpoint",
        "user": str(request.user),
        "auth": str(request.auth)
    })

  # class CityView(APIView):
  #   permission_classes = [IsAuthenticated]

  #   def post(self, request):
  #       city_id = request.data.get('city_id')
  #       if not city_id:
  #           return Response({"error": "city_id is required"}, status=status.HTTP_400_BAD_REQUEST)

  #       city = get_object_or_404(City, id=city_id)
  #       serializer = CitySerializer(city)

  #       return Response({
  #           "message": "City retrieved successfully",
  #           "user_id": request.user.id,  # Including user_id in the response
  #           "city_data": serializer.data
  #       })


@handle_exceptions
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getYear(request):
  data = parse_request_data(request)

  # Validate required fields
  error_response = validate_required_fields(data, ['year'])
  if error_response:
    return error_response

  year = safe_int_conversion(data['year'], 'year')
  if isinstance(year, JsonResponse):  # If conversion failed
    return year

  user_id = data.get('user_id') or request.user.id

  categories = Category.objects.all()
  weeks = Week.objects.filter(year__value=year).prefetch_related(
      Prefetch('weeki_set',
               queryset=Weeki.objects.filter(user_id=user_id),
               to_attr='user_weekis'))

  response = {}
  for week in weeks:
    color_array = [
        category.color for category in categories
        if any(w for w in week.user_weekis if w.category_id == category.id)
    ]
    response[str(week.value)]['week_colors'] = color_array
    response[str(week.value)]['star_date'] = week.start_date
    response[str(week.value)]['end_date'] = week.end_date

  console.log(response)
  return JsonResponse(response)


def getYearsFromProfile(request):

  year_of_birth = request.POST.get('year_of_birth')
  year_of_death = request.POST.get('year_of_death')

  try:
    years = fetch_years(year_of_birth, year_of_death)
    return JsonResponse({'years': years})
  except ValueError as e:
    return JsonResponse({'error': str(e)}, status=400)
