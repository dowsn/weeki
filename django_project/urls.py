"""
URL configuration for django_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from django.conf.urls.static import static
from app import views as app_views

# from courses import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # need to change based on authentication
    # if request.user.is_authenticated else
    path("", views.index, name="home"),
    path("home", views.index2, name="home_2"),
    path("about", views.about, name="about"),
    path('rec', views.rec, name='rec'),
    # path("create", views.article_list)
    path("blog/", include('blog.urls')),
    path('feedback/', views.feedback_view, name='feedback'),
    path('accounts/', include('accounts.urls')),
    path('on/', include('app.urls')),
    path('api/', include('api.urls')),
    path('payments/', include('payments.urls')),

    # is this a common practice?

    # path("courses", include.urls)
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
