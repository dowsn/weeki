# Generated by Django 5.1 on 2024-11-25 15:29

import app.models
import datetime
import django.db.models.deletion
import functools
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0035_topic_updates_and_chat_models'),
    ]

    operations = [
          migrations.RemoveField(
              model_name='profile',
              name='reminder_day',
          ),
          migrations.RemoveField(
              model_name='profile',
              name='sorting_descending',
          ),
          migrations.RemoveField(
              model_name='profile',
              name='mailing',
          ),
          migrations.RemoveField(
              model_name='profile',
              name='reminder_hour',
          ),
        migrations.AddField(
            model_name='profile',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=functools.partial(app.models.get_upload_path, *('profiles',), **{})),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 12, 9, 15, 29, 49, 182317, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 11, 25, 15, 29, 49, 182337, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='topic',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=functools.partial(app.models.get_upload_path, *('topics',), **{})),
        ),
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('sender', models.CharField(blank=True, max_length=200)),
                ('content', models.TextField(max_length=5000)),
                ('date_created', models.DateTimeField(auto_now_add=True, null=True)),
                ('conversation_session', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='app.conversation_session')),
            ],
        ),
    ]
