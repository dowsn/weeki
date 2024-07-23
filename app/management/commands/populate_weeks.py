from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import Year, Week  # Replace 'your_app' with your actual app name
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Empty the Week table and repopulate weeks for all years in the database'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Empty the Week table
            Week.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Emptied the Week table'))

            years = Year.objects.all()

            for year in years:
                self.stdout.write(f"Processing year {year.value}")
                year_start = date(year.value, 1, 1)
                year_end = date(year.value, 12, 31)

                # Find the first Monday of the year
                while year_start.weekday() != 0:  # 0 is Monday
                    year_start += timedelta(days=1)

                week_start = year_start
                for week_number in range(1, 53):  # Always create 52 weeks
                    if week_number == 52:
                        # For the last week, set end date to year_end
                        week_end = year_end
                    else:
                        week_end = min(week_start + timedelta(days=6), year_end)

                    Week.objects.create(
                        value=week_number,
                        year=year,
                        date_start=week_start,
                        date_end=week_end
                    )

                    if week_end == year_end:
                        break

                    week_start = week_end + timedelta(days=1)

                self.stdout.write(f"Created weeks for year {year.value}")

        self.stdout.write(self.style.SUCCESS('Successfully repopulated weeks for all years'))