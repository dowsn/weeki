from django.urls import path

from app.views import memento_mori
from . import views
from . import consumers

from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

app_name = 'api'

urlpatterns = [
    path('register', views.RegisterView.as_view(), name='register'),
    path('reset_password', views.ResetPassword.as_view(),
         name='request_reset'),
    path('cron_reminder', views.CronReminder.as_view(), name='cron_reminder'),
    path('activate_profile',
         views.VerifyActivationCode.as_view(),
         name='activate_profile'),
    path('test_mail', views.TestMail.as_view(), name='test_mail'),
    path('update_profile',
         views.UpdateProfile.as_view(),
         name='update_profile'),
    path('delete_profile', views.DeleteUser.as_view(), name='delete_profile'),
    path('send_activation_code',
         views.SendActivationCode.as_view(),
         name='send_activation_code'),
    path('chat_sessions',
         views.ChatSessionView.as_view(),
         name='chat_sessions'),
    path('register', views.RegisterView.as_view(), name='register'),
    path('model_test/', views.chats_view, name='websocket_test'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('topics', views.TopicsView.as_view(), name='topics'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
    path('login', views.LoginAPIView.as_view(), name='login'),
]
