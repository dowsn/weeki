# Generated by Django 5.1 on 2024-09-04 15:36

import datetime
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0020_alter_profile_language_alter_profile_premium_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='language',
            field=models.ForeignKey(default=1, null=True, on_delete=django.db.models.deletion.CASCADE, to='app.language'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 9, 18, 15, 36, 23, 821395, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 9, 4, 15, 36, 23, 821414, tzinfo=datetime.timezone.utc)),
        ),
    ]
