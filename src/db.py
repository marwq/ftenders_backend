from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from src.config import settings


def setup_mongo_client() -> AsyncMongoClient:
    return AsyncMongoClient(str(settings.mongo_url))


def setup_mongo_db(mongo_client: AsyncMongoClient) -> AsyncDatabase:
    return mongo_client[settings.mongo_db]
