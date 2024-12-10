from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
  dependencies = [
      ('app', '0034_alter_profile_premium_date_and_more'),
      migrations.swappable_dependency(settings.AUTH_USER_MODEL),
  ]

  operations = [
      migrations.RemoveField(
          model_name='topic',
          name='color',
      ),
      migrations.RemoveField(
          model_name='topic',
          name='summary',
      ),
      migrations.AddField(
          model_name='topic',
          name='image',
          field=models.ImageField(blank=True, null=True, upload_to='images'),
      ),
      migrations.CreateModel(
          name='Chat_Session',
          fields=[
              ('id', models.AutoField(primary_key=True, serialize=False)),
              ('day', models.IntegerField(default=1)),
              ('month', models.IntegerField(default=1)),
              ('year', models.IntegerField(default=1)),
              ('user',
               models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                 to=settings.AUTH_USER_MODEL)),
          ],
      ),
      migrations.CreateModel(
          name='Message',
          fields=[
              ('id', models.AutoField(primary_key=True, serialize=False)),
              ('content', models.TextField(blank=True, max_length=500)),
              ('date_created',
               models.DateTimeField(default=django.utils.timezone.now)),
              ('role',
               models.CharField(choices=[('user', 'User'),
                                         ('assistant', 'Assistant')],
                                max_length=10)),
              ('chat_session',
               models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                 to='app.chat_session')),
          ],
      ),
      migrations.CreateModel(
          name='Summary',
          fields=[
              ('id', models.AutoField(primary_key=True, serialize=False)),
              ('content', models.TextField(blank=True, max_length=500)),
              ('day', models.IntegerField(default=1)),
              ('month', models.IntegerField(default=1)),
              ('year', models.IntegerField(default=1)),
              ('topic',
               models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                 to='app.topic')),
          ],
      ),
      migrations.AlterField(
          model_name='profile',
          name='premium_date',
          field=models.DateField(blank=True,
                                 default=django.utils.timezone.now),
      ),
      migrations.AlterField(
          model_name='profile',
          name='premium_start',
          field=models.DateField(blank=True,
                                 default=django.utils.timezone.now),
      ),
      migrations.AlterField(
          model_name='weeki',
          name='content',
          field=models.TextField(max_length=5000),
      ),
  ]
