# Generated by Django 5.1.4 on 2025-05-13 12:22

import app.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0063_chat_session_asked_questions_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat_session',
            name='topic_names',
            field=app.models.EncryptedTextField(blank=True, max_length=1000, null=True),
        ),
    ]
