import os
import django
from django.apps import apps
from django.db import connections
from django.core.management import call_command
from django.db.models.fields import AutoField, BigAutoField
from io import StringIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

def escape_sql_string(value):
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("'", "''") + "'"

def sqlite_type_to_postgres(sqlite_type):
    type_mapping = {
        'integer': 'integer',
        'real': 'double precision',
        'text': 'text',
        'blob': 'bytea',
        'datetime': 'timestamp with time zone',
    }
    return type_mapping.get(sqlite_type.lower(), 'text')

def generate_create_table_sql(model):
    table_name = model._meta.db_table
    fields = []
    for field in model._meta.fields:
        field_type = field.db_type(connections['default'])
        if field_type:
            field_type = sqlite_type_to_postgres(field_type)
        else:
            field_type = 'text'  # default to text if we can't determine the type
        if isinstance(field, (AutoField, BigAutoField)):
            field_type = 'SERIAL PRIMARY KEY'
        nullable = 'NULL' if field.null else 'NOT NULL'
        fields.append(f"{field.column} {field_type} {nullable}")

    return f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(fields) + "\n);"

def generate_sql_commands():
    connection = connections['default']

    print("Generating schema SQL...")
    schema_sql = []

    for model in apps.get_models():
        if model._meta.managed:
            schema_sql.append(generate_create_table_sql(model))
            print(f"Generated schema for {model.__name__}")

    print("\nGenerating data SQL...")
    data_sql = []
    with connection.cursor() as cursor:
        for model in apps.get_models():
            if model._meta.managed:
                table_name = model._meta.db_table
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                if rows:
                    columns = [col[0] for col in cursor.description]
                    for row in rows:
                        values = ', '.join(map(escape_sql_string, row))
                        data_sql.append(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values});")
                print(f"Generated data for {model.__name__}: {len(rows)} rows")

    # Combine schema and data SQL, ensuring schema comes first
    full_sql = [
        "-- Disable triggers",
        "SET session_replication_role = 'replica';",
        "",
        "-- Drop all existing tables (if any)",
        "DO $$ ",
        "DECLARE ",
        "    r RECORD;",
        "BEGIN",
        "    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema()) ",
        "    LOOP",
        "        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';",
        "    END LOOP;",
        "END $$;",
        "",
        "-- Start of schema creation"
    ] + schema_sql + [
        "",
        "-- Data INSERT statements"
    ] + data_sql + [
        "",
        "-- Enable triggers",
        "SET session_replication_role = 'origin';"
    ]

    # Write SQL to file
    with open('postgres_migration.sql', 'w') as f:
        f.write('\n'.join(full_sql))

    print("\nSQL commands generated and saved to 'postgres_migration.sql'")

if __name__ == "__main__":
    generate_sql_commands()