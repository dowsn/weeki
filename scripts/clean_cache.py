import os
import shutil
from datetime import datetime, timedelta


def get_size(start_path='.'):
  total_size = 0
  for dirpath, dirnames, filenames in os.walk(start_path):
    for f in filenames:
      fp = os.path.join(dirpath, f)
      try:
        total_size += os.path.getsize(fp)
      except (FileNotFoundError, PermissionError) as e:
        print(f"Error accessing {fp}: {e}")
  return total_size


def clean_cache(cache_dir, days_old=7):
  if not os.path.exists(cache_dir):
    print(f"The directory {cache_dir} does not exist.")
    return

  print(f"Cleaning cache directory: {cache_dir}")
  print(f"Removing files older than {days_old} days")

  total_removed = 0
  total_size_removed = 0
  cutoff_date = datetime.now() - timedelta(days=days_old)

  for root, dirs, files in os.walk(cache_dir, topdown=False):
    for name in files:
      file_path = os.path.join(root, name)
      try:
        file_stat = os.stat(file_path)
        if datetime.fromtimestamp(file_stat.st_mtime) < cutoff_date:
          file_size = os.path.getsize(file_path)
          os.remove(file_path)
          total_removed += 1
          total_size_removed += file_size
          print(f"Removed: {file_path}")
      except (FileNotFoundError, PermissionError) as e:
        print(f"Error processing {file_path}: {e}")

    for name in dirs:
      dir_path = os.path.join(root, name)
      try:
        if not os.listdir(dir_path):  # Check if directory is empty
          os.rmdir(dir_path)
          print(f"Removed empty directory: {dir_path}")
      except (FileNotFoundError, PermissionError) as e:
        print(f"Error processing directory {dir_path}: {e}")

  print(f"\nTotal files removed: {total_removed}")
  print(f"Total space freed: {total_size_removed / (1024*1024):.2f} MB")


def main():
  cache_dir = os.path.join('.', '.cache')

  # Get initial size
  initial_size = get_size(cache_dir)
  print(f"Initial size of .cache: {initial_size / (1024*1024):.2f} MB")

  # Clean cache
  clean_cache(cache_dir)

  # Get final size
  final_size = get_size(cache_dir)
  print(f"Final size of .cache: {final_size / (1024*1024):.2f} MB")
  print(
      f"Total space saved: {(initial_size - final_size) / (1024*1024):.2f} MB")


if __name__ == "__main__":
  main()
