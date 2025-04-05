from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_CONNECTION_STRING")

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGO_DETAILS)
    await client.server_info()
    logger.info("Database Connected")


async def close_db():
    global client
    if client:
        client.close()
        logger.info("Database Disconnected")


def get_game_collection():
    return client.quizblitz.games
