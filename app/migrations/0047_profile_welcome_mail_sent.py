# Generated by Django 5.1.4 on 2024-12-25 09:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0046_chat_session_first'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='welcome_mail_sent',
            field=models.BooleanField(default=False),
        ),
    ]
