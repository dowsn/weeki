import psycopg2
import sys

print("Python version:", sys.version)
print("Python executable:", sys.executable)
print("psycopg2 in sys.modules:", 'psycopg2' in sys.modules)
print("psycopg2 details:", sys.modules['psycopg2'])
print("psycopg2 path:", getattr(psycopg2, '__file__', 'Not available'))
print("psycopg2 properties:", dir(psycopg2))