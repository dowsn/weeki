# Generated by Django 5.1.4 on 2025-01-01 11:52

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0050_alter_topic_date_created_alter_topic_date_updated'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PastCharacters',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('character', models.TextField(blank=True, max_length=2000)),
                ('date_created', models.DateField(auto_now_add=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PastTopics',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, max_length=2000)),
                ('title', models.TextField(blank=True, max_length=2000)),
                ('date_created', models.DateField(auto_now_add=True, null=True)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.topic')),
            ],
        ),
    ]
