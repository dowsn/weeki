from django.urls import path

from app.views import memento_mori
from . import views
from . import consumers

from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import ConversationSessionView, MessageView

app_name = 'api'

urlpatterns = [
    path('get_meeting', views.get_meeting, name='get_meeting'),
    path('model_test/<model>', views.chats_view, name='websocket_test'),
    path('pinecone_test',
         views.PineconeTestView.as_view(),
         name='pinecone_test'),
    path('langchain_test', consumers.ChatConsumer.as_asgi()),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('test_sound', views.TestSound.as_view(), name='test_sound'),
    path('week', views.WeekView.as_view(), name='week'),
    path('topics', views.TopicsView.as_view(), name='topics'),
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
    path('chat-sessions/',
         ConversationSessionView.as_view(),
         name='create_session'),
    path('grok', views.GrokView.as_view(), name='grok'),
    path('chat-sessions/<int:session_id>/',
         ConversationSessionView.as_view(),
         name='get_messages'),
    path('chat-sessions/<int:session_id>/messages/',
         MessageView.as_view(),
         name='send_message'),
    path('memento_mori/', views.getMementoMori, name='getMementoMori'),
    path('update_profile', views.update_profile, name='update_profile')
]
