#!/bin/bash

echo "Running WAEC Data Collection Pipeline..."

python /app/data-preparation/run.py

python /app/rag-pipeline/main.py

if [ $? -ne 0 ]; then
    echo "WAEC Data Collection Pipeline failed! Exiting."
    exit 1
fi

exec uvicorn api:app --host 0.0.0.0 --port 8000 --reload