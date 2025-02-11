from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from app.models import Profile, Topic, Language

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


class UserRegistrationForm(forms.ModelForm):
  password = forms.CharField(widget=forms.PasswordInput(
      attrs={'class': 'form-control'}))
  confirm_password = forms.CharField(widget=forms.PasswordInput(
      attrs={'class': 'form-control'}))

  class Meta:
    model = User
    fields = ['username', 'password']
    widgets = {
        'username': forms.TextInput(attrs={'class': 'form-control'}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields[
        'username'].help_text = "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."

  def clean(self):
    cleaned_data = super().clean()
    password = cleaned_data.get("password")
    confirm_password = cleaned_data.get("confirm_password")

    if password != confirm_password:
      raise forms.ValidationError("Passwords do not match")

    try:
      validate_password(password)
    except forms.ValidationError as error:
      self.add_error('password', error)

    return cleaned_data

  def save(self, commit=True):
    user = super().save(commit=False)
    user.set_password(self.cleaned_data["password"])
    if commit:
      user.save()
    return user


class ProfileForm(forms.ModelForm):

  class Meta:
    model = Profile
    fields = [
        'email',
        'date_of_birth',
        # 'reminder_day', 'reminder_hour'
    ]
    widgets = {
        'email':
        forms.EmailInput(attrs={'class': 'form-control'}),
        'date_of_birth':
        forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),

        # 'reminder_day':
        # forms.Select(attrs={'class': 'form-control'}),
        # 'reminder_hour':
        # forms.Select(attrs={'class': 'form-control'}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['language'].queryset = Language.objects.all()
    self.fields['language'].empty_label = None

    # Make important fields required
    self.fields['email'].required = True
    self.fields['language'].required = True
    self.fields['date_of_birth'].required = False

  def clean_email(self):
    email = self.cleaned_data.get('email')
    if email and User.objects.filter(email=email).exists():
      raise forms.ValidationError(
          "This email address is already in use. Please use a different email address."
      )
    return email


class TopicSelectionForm(forms.Form):
  # reminder_day = forms.ChoiceField(
  #     choices=Profile.REMINDER_DAY_CHOICES,
  #     widget=forms.Select(attrs={'class': 'form-select'}))
  mailing = forms.BooleanField(
      required=False,
      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    predefined_topics = [
        ('social', 'Social',
         'social interactions, relationships, acts of kindness and care, and community activities involving other people in a non-work related way. This topic includes family interactions, friendships, romantic relationships, social events, gatherings, community service, volunteer work, social clubs or groups, cultural events, team sports or group activities, social media interactions, networking events (non-professional), social support systems, and any activities that involve connecting with others for personal, emotional, or recreational purposes. GOAL: I value encompassesing meaningful connections and empathy, building a supportive network of relationships and fostering a more compassionate community.',
         '#FF5733'),
        ('productive', 'Productive',
         'work, job, freelance, tasks related to projects, work goals, project management or productivity-related topics, business-related processes, direct activities that earn money. Also includes household activities, DIY projects, and repairing of items. Additionally, this topic covers learning and skill development, financial management, health and fitness routines, time management strategies, and any activities that contribute to personal or professional growth and efficiency. GOAL: I empower value creation and growth, maximizing potential to build a long-term success and a purposeful life.',
         '#33FF57'),
        ('myself', 'Myself',
         'personal experiences, thoughts, self-reflection, and self-development. This topic doesn’t involve casual social leisure activities with other people. It includes introspection, personal goal-setting, mental health practices, meditation, journaling, self-analysis, exploring personal values and beliefs, tracking personal progress, addressing personal challenges, developing self-awareness, and cultivating habits for personal growth. It may reference others only as examples for realizing insights GOAL: I nurture deep self-awareness and growth, fostering an authentic, purposeful life through intentional self-development practices and introspection.',
         '#3357FF'),
    ]
    for i, (key, name, description, color) in enumerate(predefined_topics):
      self.fields[f'topic_{i+1}'] = forms.BooleanField(
          label=name,
          required=False,
          widget=forms.CheckboxInput(
              attrs={
                  'class': 'form-check-input',
                  'data-description': description,
                  'data-color': color
              }),
          initial=True)
    for i in range(3, 6):
      self.fields[f'topic_{i+1}'] = forms.CharField(
          required=False,
          widget=forms.TextInput(attrs={
              'class': 'form-control',
              'placeholder': f'Custom Topic {i+1}'
          }),
      )
      self.fields[f'topic_{i+1}_color'] = forms.CharField(
          required=False,
          widget=forms.TextInput(attrs={
              'type': 'color',
              'class': 'form-control form-control-color'
          }),
          initial='#000000')
