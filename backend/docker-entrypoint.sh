#!/bin/bash
set -e

echo "Running Docker Entrypoint Script"

COLLECTION_NAME="processed_questions"

cat <<EOF > /app/check_data.py
import os
import pymongo
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_data(collection):
    try:
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB_NAME")

        client = pymongo.MongoClient(mongo_uri)
        db = client[mongo_db_name]
        collection = db[COLLECTION_NAME]
        count = collection.count_documents({})
        client.close()
        return count
    except Exception as e:
        logger.error(f"Error checking MongoDB data: {e}")
        return 0

if __name__ == "__main__":
    COLLECTION_NAME = "processed_questions"
    doc_count = check_data(COLLECTION_NAME)
    if doc_count == 0:
        logger.info(f"Collection '{COLLECTION_NAME}' is empty.")
        exit(1)
    else:
        logger.info(f"Collection '{COLLECTION_NAME}' contains {doc_count} documents. Skipping data collection.")
        exit(0) 
EOF


export MONGO_URI=${MONGO_URI}
export MONGO_DB_NAME=${MONGO_DB_NAME}
export DATA_COLLECTION_NAME=${COLLECTION_NAME}

if python /app/check_data.py; then
    echo "Data already exists. Skipping data collection pipeline."
else
    echo "No data found or error checking data. Running data collection pipeline..."
    python /app/data-preparation/run.py 
    echo "Data collection pipeline finished."
fi

rm /app/check_data.py

exec uvicorn rag_pipeline.main:app --host 0.0.0.0 --port 8000 --workers 1

