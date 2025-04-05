from fastapi import Depends, FastAPI, WebSocket
from app.api import host
from app.services.game_service import GameService, QuizService
from app.websocket import host_ws, player_ws
from app.database.database import connect_db, close_db, get_game_collection
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
quiz_service = QuizService()
game_service = GameService(quiz_service=quiz_service)


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Kahoot Server!"}


@app.on_event("startup")
async def startup_event():
    await connect_db()


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()


quiz_service = QuizService()


async def get_game_service(game_collection=Depends(get_game_collection)):
    return GameService(quiz_service=quiz_service, game_collection=game_collection)


app.include_router(host.router, prefix="/api/host", tags=["host"])


@app.websocket("/ws/join/{game_pin}")
async def websocket_endpoint(websocket: WebSocket, game_pin: str):
    await player_ws.player_websocket(websocket, game_pin)


@app.websocket("/ws/host/{game_pin}")
async def host_websocket_endpoint(websocket: WebSocket, game_pin: str):
    await host_ws.host_websocket(websocket, game_pin)
