from django.contrib import admin
from .models import (AppFeedback, Chat_Session, Log, Profile, Topic, Prompt,
                     AIModel, Prompt_Debug, PastTopics, PastCharacters,
                     Message, Summary, SessionTopic)
from .models import ErrorLog
from django.conf import settings


class SecureAdmin(admin.ModelAdmin):

  def get_queryset(self, request):
    # If SHOW_ADMIN_DATA is True, show data, otherwise hide it
    qs = super().get_queryset(request)
    if getattr(settings, 'SHOW_ADMIN_DATA', False):
      return qs
    return qs.none()

  def has_view_permission(self, request, obj=None):
    return getattr(settings, 'SHOW_ADMIN_DATA', False)

  def has_change_permission(self, request, obj=None):
    return getattr(settings, 'SHOW_ADMIN_DATA', False)


# Keep ErrorLog as is since it's for debugging
@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
  list_display = ('timestamp', 'url', 'error_message', 'user')
  list_filter = ('timestamp', 'user')
  search_fields = ('url', 'error_message', 'additional_data')
  readonly_fields = ('timestamp', 'url', 'error_message', 'stack_trace',
                     'user', 'additional_data')

  def has_add_permission(self, request):
    return False

  def has_change_permission(self, request, obj=None):
    return False


# Inline admin for SessionTopic
class SessionTopicInline(admin.TabularInline):
  model = SessionTopic
  extra = 0
  fields = ('topic', 'status', 'confidence')
  readonly_fields = ('confidence', )


# Custom admin for Chat_Session with useful fields
@admin.register(Chat_Session)
class ChatSessionAdmin(SecureAdmin):
  # ✅ Fix: Add comma to make it a proper tuple
  list_display = ('id', 'user', 'title', 'time_left', 'first', 'character',
                  'summary')  # Removed 'topics'
  list_filter = ('first', 'user')
  search_fields = ('title', 'summary', 'user__username')
  # ✅ Fix: Add comma for single-item tuple
  readonly_fields = ('character', )  # Note the comma
  inlines = [SessionTopicInline]

  fieldsets = (
      ('Basic Info', {
          'fields': ('user', 'title', 'first')
      }),
      ('Session Details', {
          'fields': ('time_left', 'summary', 'character', 'topic_names')
      }),
  )

  def get_queryset(self, request):
    # Use SecureAdmin's behavior to hide in production
    return super().get_queryset(request)


# Separate admin for SessionTopic
@admin.register(SessionTopic)
class SessionTopicAdmin(SecureAdmin):
  list_display = ('session', 'topic', 'status', 'confidence')
  list_filter = ('status', 'session__user')
  search_fields = ('session__title', 'topic__name', 'session__user__username')
  readonly_fields = ('confidence', )

  def get_queryset(self, request):
    # Use SecureAdmin's behavior to hide in production
    return super().get_queryset(request)


# Register all models with SecureAdmin
admin.site.register(Profile, SecureAdmin)
# Chat_Session is registered above with custom admin
admin.site.register(Log, SecureAdmin)
admin.site.register(Message, SecureAdmin)
admin.site.register(Summary, SecureAdmin)
admin.site.register(Prompt, SecureAdmin)
admin.site.register(AIModel, SecureAdmin)
admin.site.register(AppFeedback, SecureAdmin)
admin.site.register(Prompt_Debug, SecureAdmin)
admin.site.register(PastTopics, SecureAdmin)
admin.site.register(PastCharacters, SecureAdmin)
admin.site.register(Topic, SecureAdmin)
