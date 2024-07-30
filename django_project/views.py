from django.http import HttpResponse
from django.shortcuts import render, redirect
from app import views as app_views


def index(request):
  if request.user.is_authenticated:
    return redirect('app:week')
  else:
    return render(request, "homepage.html", {})


def about(request):
  return render(request, "about.html", {})

def rec(request):
  return render(request, "rec.html", {})