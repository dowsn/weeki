from django.contrib import admin
from .models import (AppFeedback, Chat_Session, Log, Profile, Topic, Prompt,
                     AIModel, Prompt_Debug, PastTopics, PastCharacters,
                     Message, Summary)
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


# Custom admin for Chat_Session with useful fields
@admin.register(Chat_Session)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'date_created', 'is_active', 'time_left', 'first')
    list_filter = ( 'first', 'date_created', 'user')
    search_fields = ('title', 'summary', 'user__username')
    readonly_fields = ('date_created', 'character')

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'title',  'first')
        }),
        ('Session Details', {
            'fields': ('time_left', 'summary', 'character', 'topic_names')
        }),
        ('Metadata', {
            'fields': ('date_created',)
        }),
    )

    def get_queryset(self, request):
        # Always show data for Chat_Session regardless of SHOW_ADMIN_DATA
        return super(admin.ModelAdmin, self).get_queryset(request)

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
