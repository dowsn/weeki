import os
import sys
import json
import django
from django.core.management import call_command
from django.db import connections
from django.conf import settings
from django.db.utils import load_backend

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")

# Initialize Django
django.setup()


def dump_current_data():
  print("Dumping current data...")
  with open('data_dump.json', 'w') as f:
    call_command('dumpdata',
                 '--all',
                 '--indent',
                 '2',
                 exclude=['contenttypes', 'auth.permission'],
                 stdout=f)

  # Check the contents of the dump
  with open('data_dump.json', 'r') as f:
    data = json.load(f)
    model_counts = {}
    for item in data:
      model = item['model']
      model_counts[model] = model_counts.get(model, 0) + 1
    print("Objects per model:")
    for model, count in model_counts.items():
      print(f"  {model}: {count}")


def load_postgres_data():
  print("Loading data into PostgreSQL...")
  call_command('loaddata', 'data_dump.json')


def migrate_data():
  current_db = connections['default'].vendor
  print(f"Current database engine: {current_db}")

  # Dump data from current database
  dump_current_data()

  if current_db != 'postgresql':
    print(
        "This script is intended to be run when PostgreSQL is already configured."
    )
    print(
        "Please update your settings to use PostgreSQL and run this script again."
    )
    return

  # Run migrations
  print("Running migrations...")
  call_command('migrate')

  # Load data into PostgreSQL
  load_postgres_data()

  print("Migration complete!")

  # Verify data in PostgreSQL
  from django.apps import apps
  for model in apps.get_models():
    count = model.objects.count()
    print(f"{model.__name__}: {count} objects")


if __name__ == "__main__":
  migrate_data()
