# Generated by Django 5.1.4 on 2025-05-12 10:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0060_remove_topic_confidence'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chat_session',
            name='chars_since_check',
        ),
    ]
