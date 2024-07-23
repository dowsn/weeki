from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'api'

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('getYearsFromProfile/',
         views.getYearsFromProfile,
         name='getYearsFromProfile'),
    path('getYear', views.getYear, name='getYear'),
    path('getCategoriesWithWeekis',
         views.CategoriesWithWeekis.as_view(),
         name='CategoriesWithWeekis'),
    path('getYear2', views.getYear2.as_view(), name='getYear2'),
]
