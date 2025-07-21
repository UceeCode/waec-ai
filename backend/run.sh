#!/bin/bash

echo "Running WAEC Data Collection and Retrieval Pipeline..."

# python /app/data-preparation/run.py


if [ $? -ne 0 ]; then
    echo "WAEC Data Collection Pipeline failed! Exiting."
    exit 1
fi

exec uvicorn rag_pipeline.main:app --host 0.0.0.0 --port 8000