from . import models
from django import forms
from .models import Weeki, Week, Topic, Language, Profile, User, AppFeedback
from django.forms.utils import flatatt  # Correct import for flatatt
from django.utils.safestring import mark_safe  # Correct import for mark_safe
from django.forms.utils import flatatt
from django.contrib.auth.forms import UserChangeForm
from django.core.exceptions import ValidationError


class AppFeedbackForm(forms.ModelForm):

  class Meta:
    model = AppFeedback
    fields = '__all__'
    widgets = {
        'main_purpose': forms.Textarea(attrs={'rows': 4}),
        'most_confusing': forms.Textarea(attrs={'rows': 4}),
        'favorite_feature': forms.Textarea(attrs={'rows': 4}),
        'missing_function': forms.Textarea(attrs={'rows': 4}),
        'user_comment': forms.Textarea(attrs={'rows': 4}),
    }


class TopicForm(forms.ModelForm):

  class Meta:
    model = Topic
    fields = ['name', 'description', 'active']
    widgets = {
        'description': forms.Textarea(attrs={'rows': 3}),
    }

  def __init__(self, *args, **kwargs):
    self.user = kwargs.pop('user', None)
    super().__init__(*args, **kwargs)

  def clean_active(self):
    active = self.cleaned_data.get('active')
    if active and self.instance.pk is None:  # New topic
      active_topics_count = Topic.objects.filter(user=self.user,
                                                 active=True).count()
      if active_topics_count >= 6:
        raise forms.ValidationError(
            "You already have 6 active topics. Please make one inactive before activating this one."
        )
    return active


class ContentEditableDiv(forms.Widget):

  def __init__(self, attrs=None):
    default_attrs = {
        'contenteditable': 'true',
        'placeholder': 'Your experience found its playground...',
        'class': 'text-only-div',
        'dir': 'ltr',
        'style': 'text-align: left; white-space: pre-wrap;'
    }
    if attrs:
      default_attrs.update(attrs)
    super().__init__(default_attrs)

  def render(self, name, value, attrs=None, renderer=None):
    value = value or ''
    if attrs:
      self.attrs.update(attrs)
    self.attrs['name'] = name
    final_attrs = flatatt(self.attrs)
    return mark_safe(f'<div {final_attrs}>{value}</div>')


class Media:
  js = ('js/text_only_div.js', )


class FavoriteStarWidget(forms.CheckboxInput):

  def render(self, name, value, attrs=None, renderer=None):
    final_attrs = self.build_attrs(self.attrs, attrs)
    final_attrs['type'] = 'checkbox'
    final_attrs['name'] = name
    if value:
      final_attrs['checked'] = 'checked'
    return mark_safe(f'<label class="favorite-star-label">'
                     f'<input {flatatt(final_attrs)}>'
                     f'<span class="favoriteStar">★</span>'
                     f'</label>')


class NewWeekiForm(forms.ModelForm):
  content = forms.CharField(
      widget=forms.Textarea(
          attrs={
              'class': 'form-control newWeekiText',
              'style': 'height: 100%; direction: ltr; text-align: left;',
              'placeholder': 'Your experience found its playground...',
              'rows': 5,
          }),
      label='',
  )
  week_id = forms.IntegerField(widget=forms.HiddenInput())

  class Meta:
    model = Weeki
    fields = ['content', 'favorite', 'week_id']
    widgets = {
        'favorite':
        forms.CheckboxInput(attrs={'class': 'favorite-star-input'}),
    }

  def clean_content(self):
    content = self.cleaned_data.get('content')
    # Simple cleaning: just strip whitespace
    return content.strip() if content else ''


class EditWeekiForm(forms.ModelForm):
  content = forms.CharField(
      widget=ContentEditableDiv(
          attrs={
              'class': 'form-control editWeekiText',
              'style': 'height: 100%;',
              'placeholder': 'Your experience found its playground...'
          }),
      label='',
  )
  favorite = forms.BooleanField(
      widget=FavoriteStarWidget(attrs={'class': 'favorite-star-input'}),
      required=False)
  topic = forms.ModelChoiceField(queryset=Topic.objects.filter(active=True),
                                 widget=forms.HiddenInput(),
                                 required=True)

  class Meta:
    model = Weeki
    fields = ['content', 'favorite', 'topic']

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if self.instance.pk:
      self.initial['topic'] = self.instance.topic.id


class PasswordChangeForm(forms.Form):
  old_password = forms.CharField(widget=forms.PasswordInput(), required=True)
  new_password = forms.CharField(widget=forms.PasswordInput(), required=True)
  new_password_repeat = forms.CharField(widget=forms.PasswordInput(),
                                        required=True)

  def clean(self):
    cleaned_data = super().clean()
    new_password = cleaned_data.get("new_password")
    new_password_repeat = cleaned_data.get("new_password_repeat")

    if new_password and new_password_repeat and new_password != new_password_repeat:
      raise ValidationError("New passwords don't match")

    return cleaned_data


class UserSettingsForm(UserChangeForm):

  class Meta:
    model = User
    fields = ['username']

  def clean(self):
    cleaned_data = super().clean()
    if 'username' in cleaned_data:
      cleaned_data = {'username': cleaned_data['username']}
    return cleaned_data


class ProfileFormLater(forms.ModelForm):

  class Meta:
    model = Profile
    fields = [
        'email',
        'date_of_birth',
        # 'sorting_descending',
        # 'reminder_day',
        # 'reminder_hour',
        # 'mailing',
    ]
    widgets = {
        'date_of_birth':
        forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        # 'final_age':
        # forms.Select(attrs={'class': 'form-select'}),
        # 'sorting_descending':
        # forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        # 'reminder_day':
        # forms.Select(attrs={'class': 'form-select'}),
        # 'reminder_hour':
        # forms.Select(attrs={'class': 'form-select'}),
        # 'mailing':
        # forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def clean(self):
    cleaned_data = super().clean()
    print(f"Cleaned form data: {cleaned_data}")
    return cleaned_data


# If you need any additional initialization, add it here

# Additional customizations can be added here if needed
# For example, you could order the weeks or topics:
# self.fields['week'].queryset = Week.objects.order_by('-date_start')
# self.fields['topic'].queryset = Topic.objects.order_by('name')

# class BlogForm(forms.ModelForm):
#   title = forms.CharField(label="", widget=forms.TextInput(attrs=('placeholder': "Blog Title"))
#   content = forms.CharFiled(label="")
#   class Meta:
#     model = Blog
#     fields = [
#       'title',
#       'author'
#       'content',
#       'images'
#     ]
