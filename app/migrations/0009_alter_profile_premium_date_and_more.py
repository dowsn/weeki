# Generated by Django 5.1 on 2024-08-24 11:54

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_prompt_max_tokens_alter_profile_premium_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 8, 31, 11, 54, 8, 212345, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 8, 24, 11, 54, 8, 212366, tzinfo=datetime.timezone.utc)),
        ),
    ]
