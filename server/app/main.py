from fastapi import FastAPI
from app.api import host
from app.services.game_service import GameService, QuizService
from app.websocket import host_ws, player_ws

app = FastAPI()
quiz_service = QuizService()
game_service = GameService(quiz_service=quiz_service)


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Kahoot Server!"}


app.include_router(host.router, prefix="/api/host", tags=["host"])

app.add_websocket_route("/ws/host/{game_pin}", host_ws.host_websocket)
app.add_websocket_route("/ws/join/{game_pin}", player_ws.player_websocket)
