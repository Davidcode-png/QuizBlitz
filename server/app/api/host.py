from fastapi import APIRouter, Depends
from app.services.game_service import GameService, get_game_service

router = APIRouter()


@router.post("/new")
async def create_new_game(game_service: GameService = Depends(get_game_service)):
    game_pin = await game_service.create_game()
    return {"game_pin": game_pin}


@router.get("/list-games")
async def get_all_active_games(game_service: GameService = Depends(get_game_service)):
    games = game_service._get_all_active_games()
    return {"games": games}
