from fastapi import Depends, FastAPI, WebSocket, HTTPException, status
from app.api import host
from app.services.game_service import GameService, QuizService
from app.database.database import connect_db, close_db, get_game_collection
from dotenv import load_dotenv
import logging
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


from app.websocket import host_ws, player_ws


async def get_game_service(game_collection=Depends(get_game_collection)):
    return GameService(quiz_service=quiz_service, game_collection=game_collection)


app.include_router(host.router, prefix="/api/host", tags=["host"])


@app.websocket("/ws/join/{game_pin}")
async def websocket_endpoint(websocket: WebSocket, game_pin: str):
    await player_ws.player_websocket(websocket, game_pin)


@app.websocket("/ws/host/{game_pin}")
async def host_websocket_endpoint(websocket: WebSocket, game_pin: str):
    await host_ws.host_websocket(
        websocket, game_pin, GameService(quiz_service=quiz_service)
    )


@app.get("/game/{game_pin}/status")
async def get_game_status(
    game_pin: str, game_service: GameService = Depends(get_game_service)
):
    game_data = await game_service.get_game_data_from_db(game_pin)
    if not game_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with pin {game_pin} not found",
        )
    return {
        "game_pin": game_pin,
        "status": game_data.get("game_status", "unknown"),
        "player_count": len(game_data.get("players", [])),
        "current_question_index": game_data.get("current_question_index", 0),
    }
