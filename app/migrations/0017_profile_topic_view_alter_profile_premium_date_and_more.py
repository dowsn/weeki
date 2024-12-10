# Generated by Django 5.1 on 2024-08-31 12:49

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_rename_session_conversation_conversation_session_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='topic_view',
            field=models.CharField(choices=[('weekis', 'Weekis'), ('conversations', 'Conversations')], default='weekis', max_length=13),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 9, 7, 12, 49, 21, 45640, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 8, 31, 12, 49, 21, 45659, tzinfo=datetime.timezone.utc)),
        ),
    ]
