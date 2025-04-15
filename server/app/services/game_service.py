import json
from typing import Dict, List, Optional
import uuid
from fastapi import WebSocket, status

# from starlette.websockets import WebSocket
from app.models.game import GameState
from app.database.database import get_game_collection
from app.models.player import Player
from app.models.question import Question
from app.services.quiz_service import QuizService
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def get_game_service():
    game_collection = get_game_collection()
    return GameService(game_collection=game_collection)


class GameService:
    def __init__(
        self,
        quiz_service: Optional[QuizService] = None,
        game_collection: AsyncIOMotorCollection = None,
    ):
        self.active_connections: Dict[str, GameState] = {}
        self.active_games: Dict[str, GameState] = {}
        self.quiz_service = quiz_service or QuizService()
        self.game_collection = game_collection

    def _get_db_projection(self):
        return {"_id": 0}

    async def create_game(self) -> str:
        if not self.quiz_service:
            logger.error("Cannot create game, QuizService is not available.")
            raise ValueError("QuizService not initialized")
        if not self.game_collection:
            logger.error("Cannot create game, game_collection is not available.")
            raise ValueError("Database collection not initialized")
        game_pin = str(uuid.uuid4())[:6].upper()
        # Simple uniqueness check (consider retrying if collisions are likely)
        while await self.get_game_data_from_db(game_pin):
            game_pin = str(uuid.uuid4())[:6].upper()

        questions = self.quiz_service._get_default_quiz()

        if not questions:
            logger.error(f"No questions found for game {game_pin}")
            raise ValueError("No questions available")
        # self.active_games[game_pin] = GameState(
        #     host=None,
        #     players=[],
        #     questions=questions,
        #     current_question_index=0,
        #     game_status="waiting",
        #     player_answers={},
        #     current_question_start_time=None,
        # )
        # game_state_dict = self.active_games[game_pin].dict()
        # game_state_dict["game_pin"] = game_pin

        game_data_for_db = {
            "game_pin": game_pin,
            "players": [],  # Start with no players in DB
            "questions": [q.dict() for q in questions],  # Store question data
            "current_question_index": 0,
            "game_status": "waiting",
            "player_answers": {},
            "current_question_start_time": None,
        }

        result = await self.game_collection.insert_one(game_data_for_db)
        logger.info(
            f"Game created in DB with pin {game_pin}, Inserted ID: {result.inserted_id}"
        )
        return game_pin

    async def get_all_active_game_pins(self) -> List[str]:
        """Retrieves a list of all game pins from the database."""
        if not self.game_collection:
            logger.error("get_all_active_game_pins: game_collection is not set!")
            return []
        cursor = self.game_collection.find({}, {"game_pin": 1, "_id": 0})
        pins = [doc["game_pin"] async for doc in cursor]
        logger.debug(f"Fetched active game pins from DB: {pins}")
        return pins

    async def get_game_data_from_db(self, game_pin: str) -> Optional[dict]:
        if not self.game_collection:
            logger.error("get_game_data_from_db: game collection is not set!")
            return None
        logger.debug(f"Fetching game from the game pin {game_pin}")
        return await self.game_collection.find_one(
            {"game_pin": game_pin}, projection=self._get_db_projection
        )

    async def _update_game_state_in_db(self, game_pin: str, update_data: dict):
        if not self.game_collection:
            logger.error("_update_game_state_in_db: game collection is not set!")
            return None
        logger.debug(f"Updating DB for game {game_pin}: {update_data}")
        result = await self.game_collection.update_one(
            {"game_pin": game_pin}, {"$set": update_data}
        )
        logger.debug(
            f"DB update result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _push_player_to_db(self, game_pin: str, player_data: dict):
        if not self.game_collection:
            logger.error("_push_player_to_db: game_collection is not set!")
            return None
        logger.debug(
            f"Adding player {player_data.get('nickname')} to DB for game {game_pin}"
        )
        result = await self.game_collection.update_one(
            {"game_pin": game_pin}, {"$push": {"players": player_data}}
        )
        logger.debug(
            f"DB push player result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _pull_player_from_db(self, game_pin: str, nickname: str):
        if not self.game_collection:
            logger.error("_pull_player_from_db: game_collection is not set!")
            return None
        logger.debug(f"Removing player {nickname} from DB for game {game_pin}")
        result = await self.game_collection.update_one(
            {"game_pin": game_pin}, {"$pull": {"players": {"nickname": nickname}}}
        )
        logger.debug(
            f"DB pull player result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _update_player_score_in_db(
        self, game_pin: str, nickname: str, new_score: int
    ):
        if not self.game_collection:
            logger.error("_update_player_score_in_db: game_collection is not set!")
            return None
        logger.debug(
            f"Updating score for player {nickname} to {new_score} in DB for game {game_pin}"
        )
        result = await self.game_collection.update_one(
            {"game_pin": game_pin, "players.nickname": nickname},
            {"$set": {"players.$.score": new_score}},
        )
        logger.debug(
            f"DB update score result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _get_or_create_active_game_state(
        self, game_pin: str
    ) -> Optional[GameState]:
        """
        Gets the GameState from active_connections or loads from DB if needed.
        Returns None if game doesn't exist in DB.
        """
        if game_pin in self.active_connections:
            return self.active_connections[game_pin]

        game_data = await self.get_game_data_from_db(game_pin)
        if not game_data:
            logger.warning(
                f"_get_or_create_active_game_state: Game {game_pin} not found in DB"
            )
            return None
        # Deserialize data from DB into GameState, Pydantic handles validation
        # Note: Websockets are NOT stored in DB, so they'll be None initially.
        # Players list from DB contains dicts, convert them to Player models
        players_from_db = [
            Player(**player_data, websocket=None)
            for player_data in game_data.get("players", [])
        ]
        questions_from_db = [
            Question(**q_data) for q_data in game_data.get("questions", [])
        ]
        game_state = GameState(
            host=None,
            players=players_from_db,
            questions=questions_from_db,
            current_question_index=game_data.get("current_question_index", 0),
            game_status=game_data.get("game_status", "waiting"),
            player_answers=game_data.get("player_answers", {}),
            current_question_start_time=game_data.get("current_question_start_time"),
        )
        self.active_connections[game_pin] = game_state
        logger.info(f"Loaded game {game_pin} from DB into active connections.")
        return game_state

    def _cleanup_active_connection(self, game_pin: str):
        """Removes a game from active_connections if no host or players are connected."""
        if game_pin in self.active_connections:
            game_state = self.active_connections[game_pin]
            has_active_players = any(
                p.websocket and p.websocket.client_state == 1
                for p in game_state.players
            )  # CLIENT STATE 1, means the client has connected
            has_active_host = game_state.host and game_state.host.client_state == 1

            if not has_active_host and not has_active_players:
                del self.active_connections[game_pin]
                logger.info(
                    f"Removed game {game_pin} from active connections (no active host/players)."
                )

    def _get_all_active_games(self) -> List[str]:
        x = get_game_collection()
        return x

    async def connect_host(self, game_pin: str, websocket: WebSocket):
        game_state = await self._get_or_create_active_game_state(
            game_pin
        )  # self.active_games.get(game_pin)
        if game_state:
            game_state.host = websocket
            logger.info(f"Host connected to game {game_pin}")
        if game_state.host and game_state.host.client_state == 1:
            logger.warning(
                f"Host connection rejected: Host already connected for game {game_pin}"
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Host already connected"
            )
            raise ValueError("Host already connected")
        else:
            raise ValueError(f"Game with pin {game_pin} not found.")

    def disconnect_host(self, game_pin: str):
        if game_pin in self.active_connections:
            game_state = self.active_connections[game_pin]
            game_state.host = None
            logger.info(f"Host disconnected from game {game_pin}")
            self._cleanup_active_connection(
                game_pin
            )  # Check if game can be removed from memory
        else:
            logger.warning(
                f"disconnect_host: Game {game_pin} not found in active connections."
            )

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
