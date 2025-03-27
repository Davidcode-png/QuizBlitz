import json
from typing import Dict, List, Optional
import uuid
from fastapi import WebSocket

# from starlette.websockets import WebSocket
from app.models.game import GameState
from app.models.player import Player
from app.models.question import Question
from app.services.quiz_service import QuizService


class GameService:
    def __init__(self, quiz_service: Optional[QuizService] = None):
        self.active_games: Dict[str, GameState] = {}
        self.quiz_service = quiz_service or QuizService()

    def create_game(self) -> str:
        game_pin = str(uuid.uuid4())[:6].upper()
        questions = self.quiz_service._get_default_quiz()

        if not questions:
            raise ValueError("No questions available")
        self.active_games[game_pin] = GameState(
            host=None,
            players=[],
            questions=questions,
            current_question_index=0,
            game_status="waiting",
            player_answers={},
            current_question_start_time=None,
        )

        return game_pin

    def _get_all_active_games(self) -> List[str]:
        return [game_code for game_code in self.active_games.keys()]

    def connect_host(self, game_pin: str, websocket: WebSocket):
        game_state = self.active_games.get(game_pin)
        if game_state:
            game_state.host = websocket
        else:
            raise ValueError(f"Game with pin {game_pin} not found.")

    def disconnect_host(self, game_pin: str):
        game_state = self.active_games.get(game_pin)
        if game_state:
            game_state.host = None

    async def _broadcast_to_host(self, game_pin: str, message: Dict):
        game_state: GameState = self.active_games.get(game_pin)
        if (
            game_state and game_state.host and game_state.host.client_state == 1
        ):  # Client state of 1 is connected
            try:
                await game_state.host.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error broadcasting to host for game {game_pin}: {e}")

    async def _broadcast_to_players(
        self, game_pin: str, message: Dict, exclude: Optional[WebSocket] = None
    ):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state:
            for player in game_state.players:
                if player.websocket != exclude and player.websocket.client_state == 1:
                    try:
                        await game_state.host.send_text(json.dumps(message))
                    except Exception as e:
                        print(
                            f"Error broadcasting to player {player.nickname} for game {game_pin}: {e}"
                        )

    async def connect_player(self, game_pin: str, websocket: WebSocket, nickname: str):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state:
            if any(player.nickname == nickname for player in game_state.players):
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Nickname already taken"})
                )
                return False
            player = Player(websocket=websocket, nickname=nickname, score=0)
            game_state.players.append(player)
            await self._broadcast_to_host(
                game_pin, {"type": "player_joined", "nickname": nickname}
            )
            await self._broadcast_to_players(
                game_pin,
                {"type": "player_joined", "nickname": nickname},
                exclude=websocket,
            )
            return True
        else:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Invalid game pin."})
            )
            return False

    async def disconnect_player(self, game_pin: str, websocket: WebSocket):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state:
            initial_player_count = len(game_state.players)
            game_state.players = [
                player for player in game_state.players if player != websocket
            ]  # Exlcuding the current websocket
            if len(game_state.players) < initial_player_count:
                nickname = next(
                    (
                        p.nickname
                        for p in game_state.players
                        if p.websocket == websocket
                    ),
                    "A player",
                )
                await self._broadcast_to_host(
                    game_pin, {"type": "player_left", "nickname": nickname}
                )
                await self._broadcast_to_players(
                    game_pin,
                    {"type": "player_left", "nickname": nickname},
                    exclude=None,
                )

    async def end_game(self, game_pin: str):
        game_state = self.active_games.get(game_pin)
        if game_state:
            game_state.game_status = "finished"
            players_data = [
                {"nickname": p.nickname, "score": p.score} for p in game_state.players
            ]
            final_results = sorted(players_data, key=lambda x: x["score"], reverse=True)
            await self._broadcast_to_host(
                game_pin, {"type": "game_over", "results": final_results}
            )
            await self._broadcast_to_players(
                game_pin, {"type": "game_over", "results": final_results}, exclude=None
            )
        elif not game_state:
            raise ValueError(f"Game with pin {game_pin} not found.")

    async def _send_current_question(self, game_pin: str):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state and game_state.current_question_index < len(game_state.questions):
            current_question: Question = game_state.questions[
                game_state.current_question_index
            ]
            question_data = {
                "type": "question",
                "question": current_question.question,
                "options": current_question.options,
            }
            await self._broadcast_to_players(game_pin, question_data, exclude=None)
            if game_state.host:
                await game_state.host.send_text(
                    json.dumps(
                        {
                            "type": "current_question_host",
                            "question": current_question.question,
                            "options": current_question.options,
                            "question_number": game_state.current_question_index + 1,
                            "total_questions": len(game_state.questions),
                        }
                    )
                )

        elif game_state:
            await self.end_game(game_pin)
        elif not game_state:
            raise ValueError(f"Game with pin {game_pin} not found.")

    async def start_quiz(self, game_pin: str, websocket: WebSocket):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state and game_state.host:
            game_state.game_status = "in_progress"
            game_state.current_question_index = 0
            await self._send_current_question(game_pin)
        elif not game_state:
            raise ValueError(f"Game with pin {game_pin} not found.")
        else:
            await game_state.host.send_text(
                json.dumps({"type": "error", "message": "No host connected."})
            )

    async def submit_answer(
        self, game_pin: str, player_websocket: WebSocket, answer_index: int
    ):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state and game_state.game_status == "in_progress":
            player = next(
                (p for p in game_state.players if p.websocket == player_websocket), None
            )
            if player:
                question_index = game_state.current_question_index
                if question_index < len(game_state.questions):
                    if game_pin not in game_state.player_answers:
                        game_state.player_answers[game_pin] = {}
                    game_state.player_answers[game_pin][player.nickname] = answer_index
        elif not game_state:
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Invalid game pin."})
            )
        else:
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Game is not in progress."})
            )

    async def next_question(self, game_pin: str):
        game_state: GameState = self.active_games.get(game_pin)
        if game_state and game_state.game_status == "in_progress":
            game_state.current_question_index += 1
            if game_state.current_question_index < len(game_state.questions):
                await self._send_current_question(game_pin)
            else:
                await self.end_game(game_pin)
        elif not game_state:
            raise ValueError(f"Game with pin {game_pin} not found.")
        else:
            await self._broadcast_to_host(
                game_pin, {"type": "error", "message": "Game is not in progress."}
            )
