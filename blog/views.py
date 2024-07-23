from django.shortcuts import render
from .models import BlogPost
from django.http import HttpResponse


def blog_list(request):
  blog_list = BlogPost.objects.all().order_by('date')

  return render(request, "blog_list.html", {"blog_list": blog_list})


def blog_detail(request, slug):
  detailed_blog = BlogPost.objects.get(slug=slug)
  return render(request, "blog_detail.html", {"blog_post": detailed_blog})
