# Generated by Django 5.1 on 2024-08-24 15:05

import datetime
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_alter_profile_premium_date_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 8, 31, 15, 5, 8, 885007, tzinfo=datetime.timezone.utc)),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_start',
            field=models.DateField(blank=True, default=datetime.datetime(2024, 8, 24, 15, 5, 8, 885029, tzinfo=datetime.timezone.utc)),
        ),
        migrations.CreateModel(
            name='Prompt_Debug',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request', models.TextField(blank=True, null=True)),
                ('response', models.TextField(blank=True, null=True)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('prompt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.prompt')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
