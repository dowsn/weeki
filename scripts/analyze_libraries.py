import os
import sys


def analyze_lib_folder(lib_dir='.pythonlibs/lib'):
  total_size = 0
  package_sizes = {}

  for root, dirs, files in os.walk(lib_dir):
    for file in files:
      file_path = os.path.join(root, file)
      size = os.path.getsize(file_path)
      total_size += size

      # Extract package name from path
      parts = root.split(os.sep)
      if len(parts) > 1:
        package = parts[1]  # Assumes lib/package_name/...
        package_sizes[package] = package_sizes.get(package, 0) + size

  print(f"Total lib folder size: {total_size/1024/1024:.2f} MB")
  print("\nLargest packages:")
  for package, size in sorted(package_sizes.items(),
                              key=lambda x: x[1],
                              reverse=True)[:20]:
    print(f"{size/1024/1024:.2f} MB\t{package}")


if __name__ == "__main__":
  analyze_lib_folder()
