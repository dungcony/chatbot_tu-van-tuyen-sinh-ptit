"""
Shared MongoDB Client - Singleton
Tat ca models dung chung 1 MongoClient duy nhat de tiet kiem connection.
"""
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

_client = None


def get_client():
    """Tra ve MongoClient (khoi tao 1 lan duy nhat)."""
    global _client
    if _client is None:
        print("Dang ket noi MongoDB...")
        _client = MongoClient(MONGO_URI)
        print(f"MongoDB da ket noi! Database: {DB_NAME}")
    return _client


def get_db():
    return get_client()[DB_NAME]
