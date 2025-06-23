from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
import uuid
import os
import secrets
import hashlib
from functools import partial
from datetime import date
from datetime import timedelta
from cryptography.fernet import Fernet
import base64
from dateutil.relativedelta import relativedelta


class EncryptedField(models.Field):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def get_fernet(self):
    key = settings.ENCRYPTION_KEY.encode()
    key = base64.urlsafe_b64encode(key.ljust(32)[:32])
    return Fernet(key)

  def get_prep_value(self, value):
    if value is None:
      return value
    f = self.get_fernet()
    return f.encrypt(str(value).encode()).decode()

  def from_db_value(self, value, expression, connection):
    if value is None:
      return value
    f = self.get_fernet()
    return f.decrypt(value.encode()).decode()

  def db_type(self, connection):
    return 'text'  # Store encrypted data as text


class EncryptedTextField(EncryptedField):

  def db_type(self, connection):
    return 'text'


class EncryptedCharField(EncryptedField):

  def db_type(self, connection):
    return 'varchar(500)'  # Encrypted data needs more space


class EncryptedEmailField(EncryptedField):

  def db_type(self, connection):
    return 'varchar(500)'


class Profile(models.Model):
  user = models.OneToOneField(User, on_delete=models.CASCADE)
  email = EncryptedEmailField(max_length=100, blank=True)
  date_of_birth = EncryptedTextField(default='2000-01-01')
  tokens = models.IntegerField(default=4)
  reminder = models.BooleanField(choices=[(True, 'True'), (False, 'False')],
                                 default=True)
  subscription_date = models.DateField(null=True, blank=True)
  activation_token = EncryptedCharField(max_length=100, blank=True, null=True)
  character = EncryptedTextField(blank=True, null=True, max_length=2000)
  activated = models.BooleanField(default=False)
  welcome_mail_sent = models.BooleanField(default=False)
  last_login = models.DateTimeField(auto_now=True)

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

  def add_tokens(self, amount):
    """Add tokens to user account"""
    self.tokens += amount
    self.save()

  def extend_subscription(self):
    """Extend subscription by 1 month from current subscription_date or today"""
    if self.subscription_date and self.subscription_date >= timezone.now(
    ).date():
      # Extend from current subscription date
      self.subscription_date = self.subscription_date + relativedelta(months=1)
    else:
      # Start from today + 1 month
      self.subscription_date = timezone.now().date() + relativedelta(months=1)
    self.save()

  @property
  def is_subscribed(self):
    """Check if user has active subscription"""
    if not self.subscription_date:
      return False
    return self.subscription_date >= timezone.now().date()


class GooglePlaySubscription(models.Model):
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  purchase_token = models.CharField(max_length=500, unique=True)
  subscription_id = models.CharField(max_length=255,
                                     default='your_monthly_subscription_id')
  product_id = models.CharField(max_length=255)
  expiry_time_millis = models.BigIntegerField()
  auto_renewing = models.BooleanField(default=True)
  order_id = models.CharField(max_length=255, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  @property
  def expiry_date(self):
    """Convert expiry_time_millis to Django datetime"""
    return timezone.datetime.fromtimestamp(self.expiry_time_millis / 1000,
                                           tz=timezone.utc).date()

  class Meta:
    verbose_name = "Google Play Subscription"
    verbose_name_plural = "Google Play Subscriptions"


class Topic(models.Model):
  id = models.AutoField(primary_key=True)
  name = EncryptedCharField(max_length=200)
  description = EncryptedTextField(max_length=2000, blank=True)
  user = models.ForeignKey(User,
                           null=True,
                           blank=True,
                           on_delete=models.SET_NULL,
                           default=1)
  active = models.BooleanField(default=True)
  date_created = models.DateField(auto_now_add=True, null=True)
  date_updated = models.DateField(auto_now=True, null=True)

  def __str__(self):
    return self.name

  class Meta:
    verbose_name_plural = "Topics"


class PastCharacters(models.Model):
  id = models.AutoField(primary_key=True)
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  character = EncryptedTextField(max_length=2000, blank=True)
  date_created = models.DateField(auto_now_add=True, null=True)


class Chat_Session(models.Model):
  id = models.AutoField(primary_key=True)
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  time_left = models.IntegerField(default=60)
  date = models.DateField(default=date.today)
  reminder_sent = models.BooleanField(default=False)
  topic_ids = EncryptedTextField(blank=True, null=True, max_length=1000)
  first = models.BooleanField(default=False)
  asked_questions = EncryptedTextField(blank=True, null=True, max_length=5000)
  topic_names = EncryptedTextField(blank=True, null=True, max_length=1000)
  title = EncryptedCharField(max_length=100, blank=True, null=True)
  potential_topic = EncryptedTextField(blank=True, null=True, max_length=5000)
  character = EncryptedTextField(blank=True, null=True, max_length=2000)
  summary = EncryptedTextField(blank=True, null=True, max_length=500)
  saved_query = EncryptedTextField(blank=True, null=True, max_length=2000)
  topics = models.ManyToManyField(Topic,
                                  through='SessionTopic',
                                  related_name='sessions')
  logs = models.ManyToManyField('Log',
                                through='SessionLog',
                                related_name='sessions')

  @property
  def cached_topics(self):
    """Get all topics with 'Cache' status for this session"""
    return Topic.objects.filter(session_topics__session=self,
                                session_topics__status=1)

  @property
  def current_topics(self):
    """Get all topics with 'Current' status for this session"""
    return Topic.objects.filter(session_topics__session=self,
                                session_topics__status=2)

  @property
  def cached_logs(self):
    """Get all logs with 'Cache' status for this session"""
    return Log.objects.filter(session_logs__session=self,
                              session_logs__status=1)

  @property
  def current_logs(self):
    """Get all logs with 'Current' status for this session"""
    return Log.objects.filter(session_logs__session=self,
                              session_logs__status=2)

  def __str__(self):
    if hasattr(self.user, 'username'):
      return f"{self.date} - {self.user.username}"
    else:
      return f"{self.date} - Unknown Username"


class Log(models.Model):
  id = models.AutoField(primary_key=True)
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  chat_session = models.ForeignKey(Chat_Session, on_delete=models.CASCADE)
  date = models.DateField(default=date.today)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
  text = EncryptedTextField(max_length=500, blank=True)


class Message(models.Model):
  id = models.AutoField(primary_key=True)
  chat_session = models.ForeignKey(Chat_Session, on_delete=models.CASCADE)
  show_in = models.BooleanField(default=True)
  content = EncryptedTextField(max_length=500, blank=True)
  date_created = models.DateTimeField(default=timezone.now)
  role = models.CharField(max_length=10,
                          choices=[('user', 'User'),
                                   ('assistant', 'Assistant')])

  def __str__(self):
    return f"{self.date_created}"


class SessionTopic(models.Model):
  """Association model between Chat_Session and Topic with status tracking"""
  STATUS_CHOICES = [
      (0, 'No'),
      (1, 'Cache'),
      (2, 'Current'),
  ]

  session = models.ForeignKey(Chat_Session,
                              on_delete=models.CASCADE,
                              related_name='session_topics')
  topic = models.ForeignKey(Topic,
                            on_delete=models.CASCADE,
                            related_name='session_topics')
  status = models.IntegerField(default=0, choices=STATUS_CHOICES)
  confidence = models.FloatField(default=0.0)

  class Meta:
    unique_together = ['session', 'topic']
    indexes = [
        models.Index(fields=['session', 'status']),
        models.Index(fields=['topic', 'status']),
    ]

  def __str__(self):
    return f"{self.session.id} - {self.topic.name} ({self.get_status_display()})"


class SessionLog(models.Model):
  """Association model between Chat_Session and Log with status tracking"""
  STATUS_CHOICES = [
      (0, 'No'),
      (1, 'Cache'),
      (2, 'Current'),
  ]

  session = models.ForeignKey(Chat_Session,
                              on_delete=models.CASCADE,
                              related_name='session_logs')
  log = models.ForeignKey(Log,
                          on_delete=models.CASCADE,
                          related_name='session_logs')
  status = models.IntegerField(default=0, choices=STATUS_CHOICES)

  class Meta:
    unique_together = ['session', 'log']
    indexes = [
        models.Index(fields=['session', 'status']),
        models.Index(fields=['log', 'status']),
    ]

  def __str__(self):
    return f"{self.session.id} - Log {self.log.id} ({self.get_status_display()})"


class PastTopics(models.Model):
  id = models.AutoField(primary_key=True)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
  description = EncryptedTextField(max_length=2000, blank=True)
  title = EncryptedTextField(max_length=2000, blank=True)
  date_created = models.DateField(auto_now_add=True, null=True)


# class EncryptedUserFields(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     first_name = EncryptedCharField(max_length=150, blank=True)
#     last_name = EncryptedCharField(max_length=150, blank=True)
#     email = EncryptedEmailField(max_length=254)
#     username = EncryptedCharField(max_length=150)

#     def __str__(self):
#         return self.user.username

# @receiver(post_save, sender=User)
# def create_or_update_encrypted_fields(sender, instance, created, **kwargs):
#     if created:
#         EncryptedUserFields.objects.create(
#             user=instance,
#             first_name=instance.first_name,
#             last_name=instance.last_name,
#             email=instance.email,
#             username=instance.username
#         )
#     else:
#         try:
#             instance.encrypteduserfields.save()
#         except EncryptedUserFields.DoesNotExist:
#             EncryptedUserFields.objects.create(
#                 user=instance,
#                 first_name=instance.first_name,
#                 last_name=instance.last_name,
#                 email=instance.email,
#                 username=instance.username
# )


def get_upload_path(folder_name, instance, filename):
  ext = filename.split('.')[-1]
  return os.path.join('images', folder_name, f'{uuid.uuid4().hex}.{ext}')


class ProfileActivationToken(models.Model):
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  token_hash = models.CharField(max_length=64)
  created_at = models.DateTimeField(auto_now_add=True)
  expires_at = models.DateTimeField()
  used = models.BooleanField(default=False)
  attempt_count = models.IntegerField(default=0)

  class Meta:
    indexes = [
        models.Index(fields=['user', 'token_hash', 'used']),
    ]

  @classmethod
  def generate_token(cls, user):
    cls.objects.filter(user=user).delete()
    # Generate 6-digit numeric token
    token = ''.join(secrets.choice('0123456789') for _ in range(6))
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = timezone.now() + timedelta(hours=24)
    activation_token = cls.objects.create(user=user,
                                          token_hash=token_hash,
                                          expires_at=expires_at)
    return token, activation_token

  @classmethod
  def verify_token(cls, token, user):
    MAX_ATTEMPTS = 5
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    try:
      activation_token = cls.objects.get(user=user,
                                         token_hash=token_hash,
                                         used=False,
                                         expires_at__gt=timezone.now())

      if activation_token.attempt_count >= MAX_ATTEMPTS:
        activation_token.used = True
        activation_token.save()
        return False, "Maximum verification attempts exceeded"

      activation_token.attempt_count += 1

      if activation_token.attempt_count >= MAX_ATTEMPTS:
        activation_token.used = True

      if activation_token.attempt_count < MAX_ATTEMPTS:
        activation_token.used = True  # Mark as used on successful verification

      activation_token.save()
      return True, "Token verified successfully"

    except cls.DoesNotExist:
      return False, "Invalid or expired token"


class Language(models.Model):
  id = models.AutoField(primary_key=True)
  code = models.CharField(max_length=5, unique=True, default="en")
  name = models.CharField(max_length=100)
  locale = models.CharField(max_length=100)

  def __str__(self):
    return str(self.name)


# class Profile(models.Model):

#   user = models.OneToOneField(User, on_delete=models.CASCADE)
#   email = models.EmailField(max_length=100, blank=True)
#   date_of_birth = models.DateField(default='2000-01-01')
#   tokens = models.IntegerField(default=4)
#   reminder = models.BooleanField(choices=[(True, 'True'), (False, 'False')],
#                                  default=True)
#   subscription_date = models.DateField(null=True, blank=True)
#   activation_token = models.CharField(max_length=100, blank=True, null=True)
#   character = models.TextField(blank=True, null=True, max_length=2000)
#   activated = models.BooleanField(default=False)
#   welcome_mail_sent = models.BooleanField(default=False)

# class Chat_Session(models.Model):
#   id = models.AutoField(primary_key=True)
#   user = models.ForeignKey(User, on_delete=models.CASCADE)
#   time_left = models.IntegerField(default=60)
#   date = models.DateField(default=date.today)
#   first = models.BooleanField(default=False)
#   title = models.CharField(max_length=100, blank=True, null=True)
#   summary = models.TextField(blank=True, null=True, max_length=500)

#   # active = models.BooleanField(default=True)

# class Message(models.Model):
#   id = models.AutoField(primary_key=True)
#   chat_session = models.ForeignKey(Chat_Session, on_delete=models.CASCADE)
#   content = models.TextField(max_length=500, blank=True)
#   date_created = models.DateTimeField(default=timezone.now)
#   role = models.CharField(max_length=10,
#                           choices=[('user', 'User'),
#                                    ('assistant', 'Assistant')])

# class Topic(models.Model):
#   id = models.AutoField(primary_key=True)
#   name = models.CharField(max_length=200)
#   description = models.TextField(max_length=2000, blank=True)
#   user = models.ForeignKey(User,
#                            null=True,
#                            blank=True,
#                            on_delete=models.SET_NULL,
#                            default=1)
#   active = models.BooleanField(default=True)
#   date_created = models.DateField(auto_now_add=True, null=True)
#   date_updated = models.DateField(auto_now=True, null=True)

# class PastCharacters(models.Model):
#   id = models.AutoField(primary_key=True)
#   user = models.ForeignKey(User, on_delete=models.CASCADE)
#   character = models.TextField(max_length=2000, blank=True)
#   date_created = models.DateField(auto_now_add=True, null=True)

# class PastTopics(models.Model):
#   id = models.AutoField(primary_key=True)
#   topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
#   description = models.TextField(max_length=2000, blank=True)
#   title = models.TextField(max_length=2000, blank=True)
#   date_created = models.DateField(auto_now_add=True, null=True)


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


# TO BE DELETED


class AIModel(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=100)
  description = models.CharField(max_length=500)

  def __str__(self):
    return f"{self.name}"


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


class PasswordResetToken(models.Model):
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  token_hash = models.CharField(max_length=64)  # SHA-256 hash
  created_at = models.DateTimeField(auto_now_add=True)
  expires_at = models.DateTimeField()
  used = models.BooleanField(default=False)

  @classmethod
  def generate_token(cls, user):
    cls.objects.filter(user=user).delete()
    # Generate 6-digit numeric token
    token = ''.join(secrets.choice('0123456789') for _ in range(6))
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = timezone.now() + timedelta(hours=24)
    activation_token = cls.objects.create(user=user,
                                          token_hash=token_hash,
                                          expires_at=expires_at)
    return token, activation_token

  @classmethod
  def verify_token(cls, token, user):
    # Hash the provided token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Find valid token
    try:
      reset_token = cls.objects.get(user=user,
                                    token_hash=token_hash,
                                    used=False,
                                    expires_at__gt=timezone.now())
      reset_token.used = True
      reset_token.save()
      return True
    except cls.DoesNotExist:
      return False


class Prompt(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=100)
  temperature = models.FloatField(default=0.5)
  description = models.TextField(blank=True, null=True)
  max_tokens = models.IntegerField(default=1000)
  model = models.ForeignKey(AIModel, on_delete=models.CASCADE, null=True)

  def __str__(self):
    return f"{self.name} - {self.model.description}"


class Prompt_Debug(models.Model):
  prompt = models.ForeignKey(Prompt, on_delete=models.DO_NOTHING)
  request = models.TextField(blank=True, null=True)
  response = models.TextField(blank=True, null=True)
  date_created = models.DateTimeField(default=timezone.now)

  def __str__(self):
    return f"{self.date_created} - {self.prompt.name}"


class Summary(models.Model):
  id = models.AutoField(primary_key=True)
  content = models.TextField(max_length=500, blank=True)
  topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
  date = models.DateTimeField(auto_now_add=True, null=True)

  def __str__(self):
    return f"{self.date_created}"


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
