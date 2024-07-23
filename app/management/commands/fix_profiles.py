from django.core.management.base import BaseCommand
from app.models import Theme  # Replace 'your_app' with your actual app name


class Command(BaseCommand):
  help = 'Add missing Theme with ID 1'

  def handle(self, *args, **options):
    Theme.objects.create(id=1,
                         name="Default Theme")  # Adjust fields as necessary
    self.stdout.write(
        self.style.SUCCESS('Successfully added missing Theme with ID 1'))
