from django.db import models


class BlogPost(models.Model):
  title = models.CharField(max_length=200)
  content = models.TextField()
  author = models.CharField(max_length=200)
  slug = models.SlugField(max_length=200, unique=True)
  date = models.DateTimeField(auto_now_add=True)
  thumb = models.ImageField(default="default.png", upload_to='blog_images', blank=True)
  

  def snippet(self, length=100):
    if (len(self.content) > length):
      return self.content[:length] + "..."
    else:
      return self.content

  def __str__(self):
    return self.title


# Create your models here.
