from django.http import HttpResponse
from django.shortcuts import render, redirect
from app import views as app_views
from app.forms import AppFeedbackForm
from app.models import AppFeedback
from django.contrib import messages


def feedback_view(request):
  if request.method == 'POST':
    form = AppFeedbackForm(request.POST)
    if form.is_valid():
      form.save()
      messages.success(request, 'Thank you for your feedback!')
      return redirect('feedback')  # Redirect to a new form
  else:
    form = AppFeedbackForm()
  return render(request, 'feedback.html', {'form': form})


def index(request):
  if request.user.is_authenticated:
    return redirect('app:week')
  else:
    return render(request, "homepage.html", {})


def index2(request):
  return render(request, "homepage.html", {})


def about(request):
  return render(request, "about.html", {})


def rec(request):
  return render(request, "rec.html", {})
