import os
import subprocess

# Retrieve the DATABASE_URL environment variable
database_url = os.getenv('DATABASE_URL')

# Parse the database URL
# Note: For simplicity, parse and provide individual components
import urllib.parse

parsed_url = urllib.parse.urlparse(database_url)
username = parsed_url.username
password = parsed_url.password
host = parsed_url.hostname
port = parsed_url.port
dbname = parsed_url.path[1:]

# Temporary environment adjustment for pg_dump to use the password
os.environ['PGPASSWORD'] = password

# Define the output file for the database dump
dump_file = "database_dump.sql"

# Use subprocess to call pg_dump
try:
  subprocess.run(
      ["pg_dump", "-h", host, "-U", username, "-d", dbname, "-f", dump_file],
      check=True,
  )
  print(f"Database dump created successfully: {dump_file}")
except subprocess.CalledProcessError as e:
  print(f"Error occurred while creating database dump: {e}")
finally:
  # Clean up the environment variable for security reasons
  del os.environ['PGPASSWORD']
