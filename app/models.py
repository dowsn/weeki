from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
import uuid
import os
from functools import partial


def get_upload_path(folder_name, instance, filename):
  ext = filename.split('.')[-1]
  return os.path.join('images', folder_name, f'{uuid.uuid4().hex}.{ext}')


class Language(models.Model):
  id = models.AutoField(primary_key=True)
  code = models.CharField(max_length=5, unique=True, default="en")
  name = models.CharField(max_length=100)
  locale = models.CharField(max_length=100)

  def __str__(self):
    return str(self.name)


class AIModel(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=100)
  description = models.CharField(max_length=500)

  def __str__(self):
    return f"{self.name}"


class Prompt(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=100)
  temperature = models.FloatField(default=0.5)
  description = models.TextField(blank=True, null=True)
  max_tokens = models.IntegerField(default=1000)
  model = models.ForeignKey(AIModel, on_delete=models.CASCADE, null=True)

  def __str__(self):
    return f"{self.name} - {self.model.description}"


class Meeting(models.Model):
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  date = models.DateTimeField(auto_now_add=True)


class Prompt_Debug(models.Model):
  prompt = models.ForeignKey(Prompt, on_delete=models.DO_NOTHING)
  request = models.TextField(blank=True, null=True)
  response = models.TextField(blank=True, null=True)
  date_created = models.DateTimeField(default=timezone.now)

  def __str__(self):
    return f"{self.date_created} - {self.prompt.name}"


class Translation(models.Model):
  key = models.CharField(max_length=100)
  language = models.ForeignKey(Language,
                               on_delete=models.CASCADE,
                               related_name='translations')
  value = models.TextField()

  class Meta:
    unique_together = ['key', 'language']
    indexes = [
        models.Index(fields=['key', 'language']),
    ]

  def __str__(self):
    return f"{self.key} - {self.language.name}"

  @classmethod
  def get_translation(cls, key, language_code):
    try:
      return cls.objects.get(key=key, language__code=language_code).value
    except cls.DoesNotExist:
      return key  # Return the key if translation is not found


class Profile(models.Model):
  FINAL_AGE_CHOICES = [(27, '27'), (50, '50'), (60, '60'), (70, '70'),
                       (80, '80'), (90, '90'), (100, '100'), (120, '120')]

  user = models.OneToOneField(User, on_delete=models.CASCADE)
  bio = models.TextField(max_length=500, blank=True)
  email = models.EmailField(max_length=100, blank=True)
  date_of_birth = models.DateField(default='2000-01-01')
  final_age = models.IntegerField(choices=FINAL_AGE_CHOICES, default=80)
  tokens = models.IntegerField(default=4)
  language = models.ForeignKey('Language',
                               on_delete=models.CASCADE,
                               default=1,
                               null=True)
  reminder = models.BooleanField(choices=[(True, 'True'), (False, 'False')],
                                 default=True)
  image = models.ImageField(upload_to=partial(get_upload_path, 'profiles'),
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
    Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
  instance.profile.save()


class Chat_Session(models.Model):
  id = models.AutoField(primary_key=True)
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  date_created = models.DateTimeField(default=timezone.now)
  date_updated = models.DateTimeField(default=timezone.now)

  def __str__(self):
    return f"{self.date_created}"


class Message(models.Model):
  id = models.AutoField(primary_key=True)
  chat_session = models.ForeignKey(Chat_Session, on_delete=models.CASCADE)
  content = models.TextField(max_length=500, blank=True)
  date_created = models.DateTimeField(default=timezone.now)
  role = models.CharField(max_length=10,
                          choices=[('user', 'User'),
                                   ('assistant', 'Assistant')])

  def __str__(self):
    return f"{self.date_created}"


class Topic(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=200)
  description = models.TextField(max_length=500, blank=True)
  user = models.ForeignKey(User,
                           null=True,
                           blank=True,
                           on_delete=models.SET_NULL,
                           default=1)
  active = models.BooleanField(default=True)
  ordering = models.IntegerField(default=0)
  date_created = models.DateTimeField(auto_now_add=True, null=True)
  image = models.ImageField(upload_to=partial(get_upload_path, 'topics'),
                            blank=True,
                            null=True)

  def __str__(self):
    return self.name

  class Meta:
    verbose_name_plural = "Topics"


class Summary(models.Model):
  id = models.AutoField(primary_key=True)
  content = models.TextField(max_length=500, blank=True)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
  date_created = models.DateTimeField(auto_now_add=True, null=True)

  def __str__(self):
    return f"{self.date_created}"


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


class AppFeedback(models.Model):
  main_purpose = models.TextField(
      verbose_name="What do you think is the main purpose of the app?")
  most_confusing = models.TextField(
      verbose_name=
      "What was the most confusing for you in the app? Why was it confusing?")
  favorite_feature = models.TextField(
      verbose_name="What feature did you enjoy the most? And why?")
  missing_function = models.TextField(
      verbose_name="What function are you missing in this app?")

  # Understandability ratings
  APP_USE_RATING = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
  TAKING_NOTES_RATING = models.IntegerField(choices=[(i, i)
                                                     for i in range(1, 6)])
  RECORDING_NOTES_RATING = models.IntegerField(choices=[(i, i)
                                                        for i in range(1, 6)])
  CHAT_WITH_MR_WEEK_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  REGISTRATION_PROCESS_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  ADDING_WEEKI_NOTE_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  DASHBOARD_ORIENTATION_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  HOMEPAGE_RATING = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
  LOGIN_PROCESS_RATING = models.IntegerField(choices=[(i, i)
                                                      for i in range(1, 6)])

  # Usefulness ratings
  MR_WEEK_CONVERSATIONS_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  ADDING_CATEGORIES_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  RECORDING_BUTTON_RATING = models.IntegerField(choices=[(i, i)
                                                         for i in range(1, 6)])
  BIG_NOTE_ACROSS_TOPICS_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  WEEKLY_NOTES_SUMMARY_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])
  DASHBOARD_PICTURE_GENERATION_RATING = models.IntegerField(
      choices=[(i, i) for i in range(1, 6)])

  user_comment = models.TextField(verbose_name="Any additional comments?",
                                  blank=True)


# TO BE DELETED


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


def get_default_user():
  return User.objects.get_or_create(
      id=getattr(settings, 'DEFAULT_CATEGORY_USER_ID', 1))[0].id


class Sum(models.Model):
  id = models.AutoField(primary_key=True)
  content = models.TextField(max_length=500, blank=True)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
  date_created = models.DateTimeField(default=timezone.now)
  week = models.ForeignKey(Week, on_delete=models.CASCADE)
  user = models.ForeignKey(User, on_delete=models.CASCADE)

  def __str__(self):
    return f"{self.date_created} - {self.topic.name}"


class Conversation_Session(models.Model):
  id = models.AutoField(primary_key=True)
  date_created = models.DateTimeField(auto_now_add=True)
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

  def __str__(self):
    return str(self.id) if self.id else "Unnamed Conversation"


class Conversation(models.Model):
  id = models.AutoField(primary_key=True)
  date_created = models.DateTimeField(auto_now_add=True, null=True)
  sender = models.CharField(max_length=200, blank=True)
  content = models.TextField(max_length=5000)
  conversation_session = models.ForeignKey(Conversation_Session,
                                           on_delete=models.CASCADE,
                                           null=True)
  date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

  def __str__(self):
    return str(
        self.date_created) if self.date_created else "Unnamed Conversation"


class Weeki(models.Model):
  id = models.AutoField(primary_key=True)
  topic = models.ForeignKey(Topic, on_delete=models.DO_NOTHING)
  favorite = models.BooleanField(default=False)

  content = models.TextField(max_length=5000)
  user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)

  week = models.ForeignKey(Week, on_delete=models.DO_NOTHING)
  date_created = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return str(self.user) if self.user else "Unnamed Weeki"


class Original_Note(models.Model):
  id = models.AutoField(primary_key=True)

  content = models.TextField(max_length=500)
  user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)

  week = models.ForeignKey(Week, on_delete=models.DO_NOTHING)
  date_created = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return str(self.user) if self.user else "Unnamed Note"
