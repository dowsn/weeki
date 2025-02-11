from django.contrib import admin
from .models import (AppFeedback, Chat_Session, Week, Profile, Weeki, Year, 
                   Topic, Language, Translation, Original_Note, Prompt, AIModel, 
                   Prompt_Debug, PastTopics, PastCharacters, Conversation, Conversation_Session, Sum, 
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

# Register all models with SecureAdmin
admin.site.register(Profile, SecureAdmin)
admin.site.register(Chat_Session, SecureAdmin)
admin.site.register(Message, SecureAdmin)
admin.site.register(Summary, SecureAdmin)
admin.site.register(Prompt, SecureAdmin)
admin.site.register(AIModel, SecureAdmin)
admin.site.register(AppFeedback, SecureAdmin)
admin.site.register(Prompt_Debug, SecureAdmin)
admin.site.register(PastTopics, SecureAdmin)
admin.site.register(PastCharacters, SecureAdmin)
admin.site.register(Topic, SecureAdmin)