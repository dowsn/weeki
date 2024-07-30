from django.contrib import admin
from .models import Week, Profile, Weeki, Year, Category, Language, Translation
from .models import ErrorLog

# Register your models here.
admin.site.register(Week)
admin.site.register(Profile)
admin.site.register(Weeki)
admin.site.register(Year)
admin.site.register(Category)
admin.site.register(Language)
admin.site.register(Translation)


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
