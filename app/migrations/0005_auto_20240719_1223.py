from django.db import migrations

def convert_to_date(apps, schema_editor):
    Week = apps.get_model('app', 'Week')
    for week in Week.objects.all():
        week.date_start = week.date_start
        week.date_end = week.date_end
        week.save()

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_rename_year_of_death_profile_final_age'),  # replace with the name of your previous migration
    ]

    operations = [
        migrations.RunPython(convert_to_date),
    ]