import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FAISS_INDEX_PATH = "faiss_index.bin"

