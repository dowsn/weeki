import os
import importlib

# Get the current directory
current_dir = os.path.dirname(__file__)

# Loop through all .py files in the current directory
for filename in os.listdir(current_dir):
  if filename.endswith('_serializers.py'):
    module_name = filename[:-3]  # Remove the .py extension
    module = importlib.import_module(f'.{module_name}', package=__name__)

    # Import all classes that end with 'Serializer'
    for attribute_name in dir(module):
      if attribute_name.endswith('Serializer'):
        globals()[attribute_name] = getattr(module, attribute_name)

# Optionally, you can still explicitly list what you want to export
__all__ = [name for name in globals() if name.endswith('Serializer')]
