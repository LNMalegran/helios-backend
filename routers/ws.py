# backend/routers/ws.py
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import jwt, JWTError
import models
from database import SessionLocal
from config import settings

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Управляет активными WebSocket-соединениями."""
    
    def __init__(self):
        # player_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Глобальная подписка: все события получают все подключённые
        self.subscribers: Set[str] = set()
        # Блокировка для потокобезопасности
        self._lock = asyncio.Lock()
    
    async def connect(self, player_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections[player_id] = websocket
            self.subscribers.add(player_id)
    
    async def disconnect(self, player_id: str):
        async with self._lock:
            self.active_connections.pop(player_id, None)
            self.subscribers.discard(player_id)
    
    async def send_personal(self, player_id: str, message: dict):
        ws = self.active_connections.get(player_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                await self.disconnect(player_id)
    
    async def broadcast(self, message: dict, exclude: str = None):
        """Рассылает сообщение всем подключённым клиентам."""
        msg_str = json.dumps(message, default=str)
        dead = []
        for player_id, ws in list(self.active_connections.items()):
            if player_id == exclude:
                continue
            try:
                await ws.send_text(msg_str)
            except Exception:
                dead.append(player_id)
        
        for player_id in dead:
            await self.disconnect(player_id)


manager = ConnectionManager()


def get_player_from_token(token: str) -> str | None:
    """Декодирует JWT и возвращает username."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


async def push_status_updates():
    """Фоновая задача: раз в секунду рассылает всем обновления статусов."""
    while True:
        await asyncio.sleep(1.0)
        if not manager.subscribers:
            continue
        
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            for player_id in list(manager.subscribers):
                player = db.query(models.Player).filter(models.Player.id == player_id).first()
                if not player:
                    continue
                
                # Импортируем здесь, чтобы избежать циклических импортов
                from security import compute_player_snapshot
                snapshot = compute_player_snapshot(player, now)
                
                # Если статус сменился на idle — обновляем БД
                if player.status in ("moving", "resting") and snapshot["status"] == "idle":
                    arrival = player.arrival_time
                    if arrival:
                        if arrival.tzinfo is None:
                            arrival = arrival.replace(tzinfo=timezone.utc)
                        if now >= arrival:
                            if player.status == "resting":
                                start = player.start_time
                                if start and start.tzinfo is None:
                                    start = start.replace(tzinfo=timezone.utc)
                                if start:
                                    hours = max(1, round((arrival - start).total_seconds() / 3600))
                                    player.stamina = min(100.0, player.stamina + hours * 15.0)
                            elif player.status == "moving" and player.route_path:
                                try:
                                    import json as _json
                                    path = _json.loads(player.route_path)
                                    if path:
                                        player.lat = path[-1][0]
                                        player.lng = path[-1][1]
                                except Exception:
                                    pass
                            
                            player.status = "idle"
                            player.start_time = None
                            player.arrival_time = None
                            player.route_path = None
                            player.last_stamina_update = now
                            db.commit()
                
                await manager.send_personal(player_id, {
                    "type": "status_update",
                    "data": snapshot
                })
        finally:
            db.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """WebSocket-эндпоинт. Требует JWT-токен в query."""
    username = get_player_from_token(token)
    if not username:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    db = SessionLocal()
    try:
        player = db.query(models.Player).filter(models.Player.username == username).first()
        if not player:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        player_id = player.id
    finally:
        db.close()
    
    await manager.connect(player_id, websocket)
    
    # Отправляем приветственное сообщение
    await manager.send_personal(player_id, {
        "type": "connected",
        "message": "Соединение с ГЕЛИОС установлено",
        "player_id": player_id
    })
    
    try:
        while True:
            # Слушаем сообщения от клиента (для будущих фич)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Здесь можно обрабатывать клиентские события
                # Например: {"type": "ping"} для keepalive
                if msg.get("type") == "ping":
                    await manager.send_personal(player_id, {"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(player_id)


async def start_background_tasks():
    """Запускается при старте приложения."""
    asyncio.create_task(push_status_updates())
