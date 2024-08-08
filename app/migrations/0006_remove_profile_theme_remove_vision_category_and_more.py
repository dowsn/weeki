# Generated by Django 5.0.2 on 2024-08-05 20:41

import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_rename_short_language_locale_language_code_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='theme',
        ),
        migrations.RemoveField(
            model_name='vision',
            name='category',
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'verbose_name_plural': 'Categories'},
        ),
        migrations.RenameField(
            model_name='category',
            old_name='default_color',
            new_name='color',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='premium',
        ),
        migrations.AddField(
            model_name='category',
            name='description',
            field=models.TextField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='category',
            name='goal',
            field=models.TextField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='category',
            name='summary',
            field=models.TextField(blank=True, max_length=5000),
        ),
        migrations.AddField(
            model_name='category',
            name='user',
            field=models.ForeignKey(blank=True, default=1, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='profile',
            name='ai_on',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='display_week_categories',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(default=datetime.datetime(2024, 8, 12, 20, 41, 14, 138461, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AddField(
            model_name='profile',
            name='reminder_day',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='profile',
            name='reminder_time',
            field=models.TimeField(default='00:00:00'),
        ),
        migrations.AddField(
            model_name='profile',
            name='session_minutes',
            field=models.IntegerField(default=30),
        ),
        migrations.AddField(
            model_name='profile',
            name='sorting_descending',
            field=models.BooleanField(default=True),
        ),
        migrations.DeleteModel(
            name='Theme',
        ),
        migrations.DeleteModel(
            name='Vision',
        ),
    ]
