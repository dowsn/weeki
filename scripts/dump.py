import os
import sys
from pathlib import Path


def get_size(path):
  total = 0
  with os.scandir(path) as it:
    for entry in it:
      if entry.is_file():
        total += entry.stat().st_size
      elif entry.is_dir():
        total += get_size(entry.path)
  return total


def human_size(size):
  for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
    if size < 1024.0:
      return f"{size:.1f} {unit}"
    size /= 1024.0


def analyze_directory(path, min_size=1024 * 1024):  # min_size = 1MB
  print(f"Analyzing: {path}")
  for item in sorted(Path(path).glob('*'),
                     key=lambda p: p.stat().st_size,
                     reverse=True):
    item_size = item.stat().st_size if item.is_file() else get_size(item)
    if item_size >= min_size:
      print(f"{human_size(item_size)}\t{item}")


if __name__ == "__main__":
  path = sys.argv[1] if len(sys.argv) > 1 else '.'
  analyze_directory(path)
