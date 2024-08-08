from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('weeki/new', views.NewWeekiView.as_view(), name='weeki_new'),
    path('weeki/', views.NewWeekiView.as_view(), name='weeki_new_redirect'),
    path('weeki/new/<int:weekID>',
         views.NewWeekiView.as_view(),
         name='weeki_new_with_weekID'),
    path('weeki/delete/<int:weeki_id>',
         views.weeki_delete_view,
         name='weeki_delete'),
    path('weeki/edit/<int:weeki_id>',
         views.EditWeekiView.as_view(),
         name="weeki_edit"),
    path('', views.index, name='index'),
    path('week/', views.week_view, name='week'),
    path('extra/memento_mori/', views.memento_mori, name='memento_mori'),
    path('week/<int:year>/<int:week>',
         views.week_view,
         name='week_with_year_and_week'),
    path('year/', views.year_view, name='year'),
    path('year/<int:year>', views.year_view, name='year_with_year'),
    path('extra/', views.extra_view, name='extra'),
    path('extra/settings/', views.app_settings, name='app_settings')
]
