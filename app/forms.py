from . import models
from django import forms
from django import forms
from .models import Weeki, Week, Category


class NewWeekiForm(forms.Form):
  content = forms.CharField(
      widget=forms.Textarea(
          attrs={
              'rows': 2,
              'cols': 50,
              'maxlength': 140,
              'placeholder': 'Your experience found its playground...',
              'class': 'form-control',  # Optional: for Bootstrap styling
          }),
      label='',  # This removes the label
  )

  week_id = forms.CharField(widget=forms.HiddenInput())


class EditWeekiForm(forms.ModelForm):
  content = forms.CharField(
      widget=forms.Textarea(
          attrs={
              'rows': 2,
              'cols': 50,
              'maxlength': 140,
              'placeholder': 'Your experience found its playground...',
              'class': 'form-control',  # Bootstrap styling
          }),
      label='',  # Remove label
  )
  category = forms.ModelChoiceField(queryset=Category.objects.all(),
                                    widget=forms.HiddenInput(),
                                    required=True)

  class Meta:
    model = Weeki
    fields = ['content', 'category']

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
