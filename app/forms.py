from . import models
from django import forms
from django import forms
from .models import Weeki, Week, Category
from django.forms.utils import flatatt  # Correct import for flatatt
from django.utils.safestring import mark_safe  # Correct import for mark_safe
from django.forms.utils import flatatt

# class ProfileForm(forms.ModelForm)


class ContentEditableDiv(forms.Widget):

  def __init__(self, attrs=None):
    default_attrs = {
        'contenteditable': 'true',
        'placeholder': 'Your experience found its playground...'
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
      widget=ContentEditableDiv(
          attrs={
              'class': 'form-control newWeekiText',
              'style': 'height: 100%;',
              'placeholder': 'Your experience found its playground...'
          }),
      label='',
  )
  week_id = forms.IntegerField(widget=forms.HiddenInput())

  class Meta:
    model = Weeki
    fields = ['content', 'favorite', 'week_id']
    widgets = {
        'favorite': FavoriteStarWidget(attrs={'class': 'favorite-star-input'}),
    }



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
            required=False
        )
        category = forms.ModelChoiceField(
            queryset=Category.objects.all().order_by('-id'),
            widget=forms.HiddenInput(),
            required=True
        )

        class Meta:
            model = Weeki
            fields = ['content', 'favorite', 'category']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.instance.pk:
                self.initial['category'] = self.instance.category.id

  # If you need any additional initialization, add it here


# Additional customizations can be added here if needed
# For example, you could order the weeks or categories:
# self.fields['week'].queryset = Week.objects.order_by('-date_start')
# self.fields['category'].queryset = Category.objects.order_by('name')

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
