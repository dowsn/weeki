from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Theme(models.Model):
  name = models.CharField(max_length=100)
  color = models.CharField(max_length=100)

  def __str__(self):
    return str(self.name)


class Language(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=100)
  short = models.CharField(max_length=100)


class Profile(models.Model):

  # add language
  user = models.OneToOneField(User, on_delete=models.CASCADE)
  bio = models.TextField(max_length=500, blank=True)
  profile_pic = models.ImageField(upload_to='profile_pics', blank=True)
  date_of_birth = models.DateField(default='2000-01-01')
  final_age = models.IntegerField(default=2050)
  premium = models.BooleanField(default=False)
  theme = models.ForeignKey(Theme,
                            on_delete=models.CASCADE,
                            blank=True,
                            null=True)
  language = models.ForeignKey(Language,
                               on_delete=models.CASCADE,
                               blank=True,
                               null=True)

  def __str__(self):
    return str(self.user)

  def get_user_profile(user_id):
    try:
      user = User.objects.get(pk=user_id)
      return user.profile
    except User.DoesNotExist:
      return None
    except Profile.DoesNotExist:
      return None


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
  if created:
    Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
  instance.profile.save()


class Year(models.Model):
  id = models.AutoField(primary_key=True)
  value = models.IntegerField(unique=False, null=True)

  def __str__(self):
    return str(self.value)


class Week(models.Model):
  id = models.AutoField(primary_key=True)
  value = models.IntegerField(unique=False, null=True)
  year = models.ForeignKey(Year, on_delete=models.DO_NOTHING)
  date_start = models.DateField()
  date_end = models.DateField()

  def __str__(self):
    return str(self.date_start) if self.date_start else "Undated week"


class Category(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=200)
  default_color = models.CharField(max_length=200)

  def __str__(self):
    return str(self.name) if self.name else "Unnamed category"


class Vision(models.Model):
  category = models.ForeignKey(Category, on_delete=models.CASCADE)
  content = models.TextField(max_length=500, blank=True)
  image = models.ImageField(upload_to='images/', blank=True)

  def __str__(self):
    return str(self.category.name)


class Weeki(models.Model):
  id = models.AutoField(primary_key=True)
  category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
  favorite = models.BooleanField(default=False)

  content = models.TextField(max_length=500)
  user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)

  week = models.ForeignKey(Week, on_delete=models.DO_NOTHING)
  date_created = models.DateTimeField(auto_now_add=True)
  image = models.ImageField(upload_to='weeki_imagery', blank=True)

  def __str__(self):
    return str(self.user) if self.user else "Unnamed Weeki"


class ErrorLog(models.Model):
  timestamp = models.DateTimeField(default=timezone.now)
  url = models.URLField(max_length=255)
  error_message = models.TextField()
  stack_trace = models.TextField(blank=True, null=True)
  user = models.ForeignKey('auth.User',
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True)
  additional_data = models.JSONField(blank=True, null=True)

  def __str__(self):
    return f"{self.timestamp} - {self.url} - {self.error_message[:50]}"
