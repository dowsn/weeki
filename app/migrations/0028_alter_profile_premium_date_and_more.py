# Generated by Django 5.1 on 2024-09-09 16:30

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0027_alter_profile_premium_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 9, 23, 16, 30, 41, 825519, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 9, 9, 16, 30, 41, 825541, tzinfo=datetime.timezone.utc)),
        ),
    ]
