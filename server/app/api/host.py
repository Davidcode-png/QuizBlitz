from typing import List
from fastapi import APIRouter, Depends
from app.services.game_service import GameService, get_game_service
from app.models.question import MessageRequest, Question

router = APIRouter()


@router.post("/new")
async def create_new_game(game_service: GameService = Depends(get_game_service)):
    game_pin = await game_service.create_game()
    return {"game_pin": game_pin}


@router.post("/new-game")
async def create_new_game(
    body: List[Question], game_service: GameService = Depends(get_game_service)
):
    game_pin = await game_service.create_game(manual=True, questions_data=body)
    return {"game_pin": game_pin}


@router.post("/generate")
async def generate_questions(
    body: MessageRequest, game_service: GameService = Depends(get_game_service)
):
    questions = game_service.generate_questions(body.message)
    return {"questions": questions}


@router.get("/list-games")
async def get_all_active_games(game_service: GameService = Depends(get_game_service)):
    games = game_service._get_all_active_games()
    return {"games": games}
