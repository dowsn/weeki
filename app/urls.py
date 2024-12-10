from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('weeki/new', views.NewWeekiView.as_view(), name='weeki_new'),
    path('weeki/', views.NewWeekiView.as_view(), name='weeki_new_redirect'),
    path('weeki/new/<int:weekID>',
         views.NewWeekiView.as_view(),
         name='weeki_new_with_weekID'),
    # path('weeki/delete/<int:weeki_id>',
    #      views.weeki_delete_view,
    #      name='weeki_delete'),
    path('weeki/edit/<int:weeki_id>',
         views.EditWeekiView.as_view(),
         name="weeki_edit"),
    path('', views.index, name='index'),
    path('week/', views.week_view, name='week'),
    path('memento_mori/', views.memento_mori, name='memento_mori'),
    path('week/<int:year>/<int:week>',
         views.week_view,
         name='week_with_year_and_week'),
    path('year/', views.year_view, name='year'),
    path('year/<int:year>', views.year_view, name='year_with_year'),
    path('build/', views.build_view, name='build'),
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.edit_profile, name='edit_profile'),
    # path('midjourney', views.midjourney, name='midjourney'),
    # path('midjourney_fetch', views.midjourney_fetch, name='midjourney_fetch'),
    # path('midjourney_download', views.download_file, name='midjourney_file'),
    path('mr_week/<str:topic>/<int:conversation_session_id>/',
         views.MrWeek.as_view(),
         name='mr_week_with_session'),
    path('mr_week/<str:topic>/', views.MrWeek.as_view(), name='mr_week'),
    path('mr_week/', views.MrWeek.as_view(), name='mr_week_default'),
    path('topics/', views.topics_view, name='topics'),
    path('topic/<str:topic_id>/', views.TopicEdit.as_view(),
         name='topic_edit'),
    path('topic/<str:topic_id>/',
         views.TopicEdit.as_view(),
         name='topic_edit_with_session'),
    path('cron_job/', views.cron_job, name='cron_job'),
    path('payment', views.payment_view, name='payment'),

    # path('build/mr_week', views.mr_week_view, name='mr_week'),
    # path('build/send_chat_message/',
    #      views.send_chat_message,
    #      name='send_chat_message')

    # path('build/topic/<str:name>', views.topic_detail_view, name='topic_detail'),
    # path('build/topics/', views.topics_view, name='topics'),
]
