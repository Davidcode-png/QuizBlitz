from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_CONNECTION_STRING")

print("MONGO DETAILS ARE", MONGO_DETAILS)
client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGO_DETAILS)
    await client.server_info()
    print("Connected to MongoDB")


async def close_db():
    global client
    if client:
        client.close()
        print("Disconnected from MongoDB")


def get_game_collection():
    return client.quizblitz.games
