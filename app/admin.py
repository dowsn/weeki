from django.contrib import admin
from .models import AppFeedback, Chat_Session, Week, Profile, Weeki, Year, Topic, Language, Translation, Original_Note, Prompt, AIModel, Prompt_Debug, Conversation, Conversation_Session, Sum, Message, Summary, Chat_Session
from .models import ErrorLog

# Register your models here.
admin.site.register(Profile)
admin.site.register(Topic)
admin.site.register(Chat_Session)
admin.site.register(Message)
admin.site.register(Summary)

admin.site.register(Prompt)
admin.site.register(AIModel)
admin.site.register(Prompt_Debug)


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
