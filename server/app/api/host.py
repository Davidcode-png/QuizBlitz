from fastapi import APIRouter, Depends
from app.services.game_service import GameService

router = APIRouter()
game_service = GameService()


@router.post("/new")
async def create_new_game():
    game_pin = game_service.create_game()
    return {"game_pin": game_pin}


@router.get("/list-games")
async def get_all_active_games():
    games = game_service._get_all_active_games()
    return {"games": games}
