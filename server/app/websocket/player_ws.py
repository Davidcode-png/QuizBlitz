from fastapi import WebSocket, WebSocketDisconnect
from fastapi import WebSocketDisconnect
import json
from app.services.game_service import GameService

game_service = GameService()


async def player_websocket(websocket: WebSocket, game_pin: str):
    await websocket.accept()
    nickname = await websocket.receive_text()
    connected = await game_service.connect_player(game_pin, websocket, nickname)
    if not connected:
        await websocket.close()
        return
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            if action == "submit_answer":
                answer_index = payload.get("answer")
                if answer_index is not None:
                    await game_service.submit_answer(game_pin, websocket, answer_index)
    except WebSocketDisconnect:
        await game_service.disconnect_player(game_pin, websocket)
        print(f"Player {nickname} disconnected from game {game_pin}")
    except Exception as e:
        print(f"Error in player websocket for game {game_pin}: {e}")
