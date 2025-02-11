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
    path('pinecone_test',
         views.PineconeTestView.as_view(),
         name='pinecone_test'),
    path('langchain_test', consumers.ChatConsumer.as_asgi()),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('test_sound', views.TestSound.as_view(), name='test_sound'),
    path('week', views.WeekView.as_view(), name='week'),
    path('topics', views.TopicsView.as_view(), name='topics'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
    path('save_note', views.SaveNoteView.as_view(), name='save_note'),
    path('suggest_question',
         views.SuggestQuestionView.as_view(),
         name='suggest_question'),
    path('week_filter', views.WeekFilter.as_view(), name='week_filter'),
    path('topic', views.TopicView.as_view(), name='topic'),
    path('topic_filter', views.TopicFilter.as_view(), name='topic_filter'),
    path('year', views.YearView.as_view(), name='year'),
    path('year_filter', views.YearFilter.as_view(), name='year_filter'),
    path('login', views.LoginAPIView.as_view(), name='login'),
    path('memento_mori/', views.getMementoMori, name='getMementoMori'),
    path('update_profile', views.update_profile, name='update_profile')
]
