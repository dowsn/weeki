# Generated by Django 5.1.4 on 2025-01-03 16:31

import app.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0053_encrypteduserfields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chat_session',
            name='summary',
            field=app.models.EncryptedTextField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='chat_session',
            name='title',
            field=app.models.EncryptedCharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='content',
            field=app.models.EncryptedTextField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name='pastcharacters',
            name='character',
            field=app.models.EncryptedTextField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name='pasttopics',
            name='description',
            field=app.models.EncryptedTextField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name='pasttopics',
            name='title',
            field=app.models.EncryptedTextField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name='profile',
            name='activation_token',
            field=app.models.EncryptedCharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='character',
            field=app.models.EncryptedTextField(blank=True, max_length=2000, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='date_of_birth',
            field=app.models.EncryptedTextField(default='2000-01-01'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='email',
            field=app.models.EncryptedEmailField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='topic',
            name='description',
            field=app.models.EncryptedTextField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name='topic',
            name='name',
            field=app.models.EncryptedCharField(max_length=200),
        ),
        migrations.DeleteModel(
            name='EncryptedUserFields',
        ),
    ]
