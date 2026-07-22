# backend/security.py
import jwt
import json
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import models
from database import get_db
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=60*24*7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


# backend/security.py — замени compute_player_snapshot на:

def compute_player_snapshot(player: models.Player, now: datetime) -> dict:
    """Чистая функция — вычисляет состояние персонажа БЕЗ побочных эффектов."""
    
    def to_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    
    arrival_time = to_utc(player.arrival_time)
    start_time = to_utc(player.start_time)

    base = {
        "status": player.status,
        "pos": [player.lat, player.lng],
        "stamina": round(player.stamina, 1),
        "route_path": [],
        "time_left": 0
    }

    if player.status == "moving" and arrival_time and start_time:
        route_path = json.loads(player.route_path) if player.route_path else []
        
        if now >= arrival_time:
            # Прибыл
            dest_coords = route_path[-1] if route_path else [player.lat, player.lng]
            return {
                "status": "idle",
                "pos": dest_coords,
                "stamina": round(player.stamina, 1),
                "route_path": [],
                "time_left": 0
            }
        
        # В пути
        total_duration = (arrival_time - start_time).total_seconds()
        elapsed_duration = (now - start_time).total_seconds()
        progress = min(1.0, max(0.0, elapsed_duration / total_duration)) if total_duration > 0 else 1.0
        
        if len(route_path) > 1:
            idx = min(len(route_path) - 1, int(progress * (len(route_path) - 1)))
            current_lat, current_lng = route_path[idx]
        else:
            current_lat = player.lat
            current_lng = player.lng
        
        return {
            "status": "moving",
            "pos": [current_lat, current_lng],
            "stamina": round(player.stamina, 1),
            "route_path": route_path,
            "time_left": int((arrival_time - now).total_seconds())
        }

    elif player.status == "resting" and arrival_time and start_time:
        if now >= arrival_time:
            total_seconds = (arrival_time - start_time).total_seconds()
            hours_rested = max(1, round(total_seconds / 3600))
            new_stamina = min(100.0, player.stamina + hours_rested * 15.0)
            return {
                "status": "idle",
                "pos": [player.lat, player.lng],
                "stamina": round(new_stamina, 1),
                "route_path": [],
                "time_left": 0
            }
        return {
            "status": "resting",
            "pos": [player.lat, player.lng],
            "stamina": round(player.stamina, 1),
            "route_path": [],
            "time_left": int((arrival_time - now).total_seconds())
        }

    return base



async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Сессия истекла или токен не валиден",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    player = db.query(models.Player).filter(models.Player.username == username).first()
    if player is None:
        raise credentials_exception
        
    # При каждом запросе фиксируем время — для пассивной регенерации
    now = datetime.now(timezone.utc)
    last_update = player.last_stamina_update
    if last_update:
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        elapsed = (now - last_update).total_seconds()
        if elapsed > 0:
            if player.status == "idle":
                player.stamina = min(100.0, player.stamina + (elapsed * 0.02))
                player.last_stamina_update = now
            elif player.status == "resting":
                player.stamina = min(100.0, player.stamina + (elapsed * 0.25))
                player.last_stamina_update = now
            # moving — стамину уже списали при старте, пассивно не трогаем
            db.commit()
    else:
        player.last_stamina_update = now
        db.commit()
    
    return player

async def require_admin(current_user: models.Player = Depends(get_current_user)):
    """Требует роль admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Доступ только для администратора системы"
        )
    return current_user


async def require_constellation_or_admin(current_user: models.Player = Depends(get_current_user)):
    """Требует роль constellation или admin."""
    if current_user.role not in ("constellation", "admin"):
        raise HTTPException(
            status_code=403, 
            detail="Доступ только для созвездий"
        )
    return current_user