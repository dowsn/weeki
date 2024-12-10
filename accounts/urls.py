from django.urls import path
from . import views
from .views import RegistrationView

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('profile/', views.profile_view, name='profile'),
    path('register/<int:step>/',
         RegistrationView.as_view(),
         name='registration_step'),
    path('register/', RegistrationView.as_view(), name='registration_start'),
]
