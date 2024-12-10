# Generated by Django 5.1 on 2024-08-19 15:56

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_remove_conversation_created_at_topic_date_created_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='reminder_hour',
            field=models.IntegerField(choices=[(0, '0'), (1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5'), (6, '6'), (7, '7'), (8, '8'), (9, '9'), (10, '10'), (11, '11'), (12, '12'), (13, '13'), (14, '14'), (15, '15'), (16, '16'), (17, '17'), (18, '18'), (19, '19'), (20, '20'), (21, '21'), (22, '22'), (23, '23')], default=12),
        ),
        migrations.AlterField(
            model_name='profile',
            name='premium_date',
            field=models.DateField(default=datetime.datetime(2024, 8, 26, 15, 56, 54, 767702, tzinfo=datetime.timezone.utc)),
        ),
    ]
