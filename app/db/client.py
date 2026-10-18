import os

from dotenv import load_dotenv
from pymongo import AsyncMongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is not configured. "
        "Add it to the project's .env file."
    )

# Fail promptly if the configured MongoDB server cannot be reached.
mongo_client = AsyncMongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    appname="DocuMindAI",
)