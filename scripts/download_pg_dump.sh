#!/bin/bash
# Define the URL and output directory
URL="https://ftp.postgresql.org/pub/source/v16.3/postgresql-16.3.tar.bz2"
OUTPUT_DIR="pg_dump_16"
# Download and extract
mkdir -p $OUTPUT_DIR
curl -o postgresql-16.3.tar.bz2 $URL
tar -xjf postgresql-16.3.tar.bz2 -C $OUTPUT_DIR --strip-components=1
# Navigate to source directory
cd $OUTPUT_DIR
# Configure the build environment
./configure --without-readline --without-zlib
# Build only pg_dump
cd src/bin/pg_dump
make
# Check if pg_dump is compiled successfully
if [[ ! -f pg_dump ]]; then
  echo "pg_dump compilation failed"
  exit 1
fi
# Make pg_dump executable
chmod +x pg_dump
echo "pg_dump compiled successfully at $(pwd)/pg_dump"