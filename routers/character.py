# backend/routers/character.py
import httpx
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import models, schemas, security
from database import get_db
from utils.geofence import is_player_inside_district
from config import settings
from routers.constellation import log_event

router = APIRouter(prefix="/character", tags=["Персонаж"])


def to_utc(dt):
    """Безопасное приведение datetime к UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/me/profile")
async def get_player_profile(current_user: models.Player = Depends(security.get_current_user)):
    return {
        "username": current_user.username,
        "role": current_user.role,  # ← ДОБАВЬ ЭТУ СТРОКУ
        "stamina": round(current_user.stamina, 1),
        "status": current_user.status,
        "coordinates": [current_user.lat, current_user.lng],
        "equipped_armor": current_user.equipped_armor.name if current_user.equipped_armor else None,
        "attributes": {
            "ST": current_user.st, 
            "DX": current_user.dx, 
            "IQ": current_user.iq, 
            "HT": current_user.ht
        }
    }


@router.get("/status")
def get_character_status(current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    """
    Единая точка истины: вычисляет текущее состояние персонажа
    И обновляет БД, если персонаж прибыл.
    """
    now = datetime.now(timezone.utc)
    snapshot = security.compute_player_snapshot(current_user, now)
    
    # === СИНХРОНИЗАЦИЯ С БД ===
    # Если снимок говорит "idle", а в БД всё ещё "moving"/"resting" — 
    # значит персонаж только что завершил действие, нужно зафиксировать.
    
    if current_user.status in ("moving", "resting"):
        arrival_time = to_utc(current_user.arrival_time)
    
    if arrival_time and now >= arrival_time:
        if current_user.status == "resting":
            start_time = to_utc(current_user.start_time)
            if start_time:
                total_seconds = (arrival_time - start_time).total_seconds()
                hours_rested = max(1, round(total_seconds / 3600))
                current_user.stamina = min(100.0, current_user.stamina + hours_rested * 15.0)
        
        # === КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: обновляем координаты на конечную точку ===
        if current_user.status == "moving" and current_user.route_path:
            try:
                route_path = json.loads(current_user.route_path)
                if route_path and len(route_path) > 0:
                    current_user.lat = route_path[-1][0]
                    current_user.lng = route_path[-1][1]
            except (json.JSONDecodeError, IndexError, TypeError):
                pass
        
        current_user.status = "idle"
        current_user.start_time = None
        current_user.arrival_time = None
        current_user.route_path = None
        current_user.last_stamina_update = now
        db.commit()
    
    return snapshot


@router.post("/move")
async def start_movement(req: schemas.MoveRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    if current_user.status == "moving":
        raise HTTPException(status_code=400, detail="Оперативник уже находится в режиме перемещения")
    if current_user.status == "resting":
        raise HTTPException(status_code=400, detail="Нельзя идти во время отдыха. Сначала прервите отдых")

    # Проверка геофенсинга
    district = db.query(models.District).filter(models.District.id == current_user.current_district_id).first()
    if not is_player_inside_district(req.target_lat, req.target_lng, district):
        raise HTTPException(status_code=400, detail="Выход за границы доступного сектора мониторинга")

    osrm_url = f"{settings.osrm_url}/route/v1/foot/{current_user.lng},{current_user.lat};{req.target_lng},{req.target_lat}?overview=full&geometries=geojson"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(osrm_url)
            data = response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Таймаут внешнего навигатора OSRM")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Сбой внешнего навигатора: {str(e)}")
            
    if "routes" not in data or len(data["routes"]) == 0:
        raise HTTPException(status_code=400, detail="Пеший маршрут не может быть проложен")
        
    route = data["routes"][0]
    raw_coords = route["geometry"]["coordinates"]
    route_path = [[coord[1], coord[0]] for coord in raw_coords]
    
    stamina_cost = route["distance"] / 25.0
    if current_user.stamina < stamina_cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно выносливости. Требуется: {round(stamina_cost, 1)} FP")
        
    current_user.stamina -= stamina_cost
    
    simulated_duration = max(6.0, route["duration"] / settings.time_speed_modifier)
    
    now = datetime.now(timezone.utc)
    current_user.status = "moving"
    current_user.route_path = json.dumps(route_path)
    current_user.start_time = now
    current_user.arrival_time = now + timedelta(seconds=simulated_duration)
    current_user.total_duration = simulated_duration
    current_user.last_stamina_update = now
    
    db.commit()
    log_event(db, current_user.id, "move", 
              f"{current_user.username} выдвинулся к ({req.target_lat:.4f}, {req.target_lng:.4f})",
              {"target": [req.target_lat, req.target_lng], "duration": int(simulated_duration)})
    db.commit()
    return {"status": "started", "time_left_seconds": int(simulated_duration)}


@router.post("/rest/start")
async def start_resting(req: schemas.RestRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    if current_user.status == "moving":
        raise HTTPException(status_code=400, detail="Нельзя лечь отдыхать на бегу")
    if current_user.status == "resting":
        raise HTTPException(status_code=400, detail="Оперативник уже на отдыхе")
    
    now = datetime.now(timezone.utc)
    current_user.status = "resting"
    current_user.start_time = now
    current_user.arrival_time = now + timedelta(hours=req.hours)
    current_user.last_stamina_update = now
    
    db.commit()
    log_event(db, current_user.id, "rest",
              f"{current_user.username} разбил лагерь на {req.hours}ч.",
              {"hours": req.hours})
    db.commit()
    return {"status": "success", "message": f"Оперативник развернул лагерь на {req.hours} ч."}


@router.post("/rest/stop")
async def stop_resting(current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    if current_user.status != "resting":
        raise HTTPException(status_code=400, detail="Оперативник не находится на отдыхе")
    
    now = datetime.now(timezone.utc)
    start_time = to_utc(current_user.start_time)
    
    elapsed_seconds = (now - start_time).total_seconds() if start_time else 0
    hours_passed = int(elapsed_seconds // 3600)
    if hours_passed > 0:
        current_user.stamina = min(100.0, current_user.stamina + (hours_passed * 15.0))
        
    current_user.status = "idle"
    current_user.start_time = None
    current_user.arrival_time = None
    current_user.last_stamina_update = now
    db.commit()
    return {"status": "success", "message": f"Оперативник поднялся на ноги. Восстановлено за {hours_passed} ч."}
