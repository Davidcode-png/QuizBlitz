from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
from app.services.game_service import GameService

game_service = GameService()


async def host_websocket(websocket: WebSocket, game_pin: str):
    await websocket.accept()
    try:
        game_service.connect_host(game_pin, websocket)
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            if action == "start_quiz":
                await game_service.start_quiz(game_pin)
            elif action == "next_question":
                await game_service.next_question(game_pin)
    except WebSocketDisconnect:
        game_service.disconnect_host(game_pin)
        print(f"Host disconnected from game {game_pin}")
    except Exception as e:
        print(f"Error in host websocket for game {game_pin}: {e}")
