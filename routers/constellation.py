# backend/routers/constellation.py
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import models, schemas, security
from database import get_db

router = APIRouter(prefix="/constellation", tags=["Созвездия"])

@router.post("/promote")
async def promote_to_constellation(
    req: schemas.ConstellationPromoteRequest,
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Игрок становится созвездием. Требует имя и титул."""
    existing = db.query(models.Constellation).filter(
        models.Constellation.player_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Вы уже являетесь созвездием")
    
    if current_user.stamina > 50:
        raise HTTPException(
            status_code=400, 
            detail=f"Необходимо исчерпать FP ниже 50 для трансценденции. Сейчас: {round(current_user.stamina, 1)}"
        )
    
    constellation = models.Constellation(
        id=f"const_{uuid.uuid4().hex[:12]}",
        player_id=current_user.id,
        name=req.name,
        title=req.title,
        influence=100,
        scenarios_watched=0
    )
    current_user.role = "constellation"
    db.add(constellation)
    db.commit()
    db.refresh(constellation)
    
    return {
        "status": "transcended",
        "constellation_id": constellation.id,
        "name": constellation.name,
        "title": constellation.title,
        "influence": constellation.influence
    }



@router.get("/me")
async def get_my_constellation(
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Получить свой профиль созвездия (если есть)."""
    constellation = db.query(models.Constellation).filter(
        models.Constellation.player_id == current_user.id
    ).first()
    
    if not constellation:
        return {"is_constellation": False}
    
    return {
        "is_constellation": True,
        "id": constellation.id,
        "name": constellation.name,
        "title": constellation.title,
        "influence": constellation.influence,
        "scenarios_watched": constellation.scenarios_watched,
        "created_at": constellation.created_at
    }


@router.get("/incarnations")
async def list_incarnations(
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Список всех воплощений (обычных игроков) для наблюдения."""
    # Проверяем, что это созвездие
    const = db.query(models.Constellation).filter(
        models.Constellation.player_id == current_user.id
    ).first()
    if not const:
        raise HTTPException(status_code=403, detail="Доступ только для созвездий")
    
    players = db.query(models.Player).filter(
        models.Player.id != current_user.id
    ).all()
    
    return [{
        "player_id": p.id,
        "username": p.username,
        "status": p.status,
        "stamina": round(p.stamina, 1),
        "coordinates": [p.lat, p.lng],
        "attributes": {"ST": p.st, "DX": p.dx, "IQ": p.iq, "HT": p.ht}
    } for p in players]


@router.post("/message")
async def send_message(
    req: schemas.ConstellationMessageRequest,
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Созвездие отправляет сообщение воплощению."""
    const = db.query(models.Constellation).filter(
        models.Constellation.player_id == current_user.id
    ).first()
    if not const:
        raise HTTPException(status_code=403, detail="Только созвездия могут отправлять сообщения")
    
    # Стоимость в зависимости от типа
    costs = {
        "whisper": 10,
        "indirect_message": 25,
        "blessing": 50,
        "warning": 15
    }
    cost = costs.get(req.message_type, 10)
    
    if const.influence < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостаточно влияния. Требуется: {cost}, доступно: {const.influence}"
        )
    
    # Проверка цели
    target_id = None
    if req.target_player_id:
        target = db.query(models.Player).filter(
            models.Player.username == req.target_player_id
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Воплощение не найдено")
        target_id = target.id
    
    # Создаём сообщение
    message = models.ConstellationMessage(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        constellation_id=const.id,
        target_player_id=target_id,
        text=req.text,
        message_type=req.message_type,
        influence_cost=cost
    )
    db.add(message)
    
    const.influence -= cost
    const.scenarios_watched += 1
    
    db.commit()
    
    # Рассылаем через WebSocket (импорт здесь чтобы избежать циклических импортов)
    from routers.ws import manager
    msg_payload = {
        "type": "constellation_message",
        "from": const.name,
        "title": const.title,
        "text": req.text,
        "message_type": req.message_type,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if target_id:
        await manager.send_personal(target_id, msg_payload)
    else:
        await manager.broadcast(msg_payload, exclude=current_user.id)
    
    return {
        "status": "sent",
        "influence_remaining": const.influence,
        "message_id": message.id
    }


@router.get("/feed")
async def get_scenario_feed(
    limit: int = Query(50, le=200),
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Лента событий — что делают все воплощения."""
    const = db.query(models.Constellation).filter(
        models.Constellation.player_id == current_user.id
    ).first()
    if not const:
        raise HTTPException(status_code=403, detail="Только созвездия могут наблюдать")
    
    logs = db.query(models.ScenarioLog).order_by(
        models.ScenarioLog.created_at.desc()
    ).limit(limit).all()
    
    return [{
        "id": log.id,
        "player_id": log.player_id,
        "action_type": log.action_type,
        "description": log.description,
        "details": log.details,
        "created_at": log.created_at
    } for log in logs]


# === Вспомогательная функция для логирования событий ===
def log_event(db: Session, player_id: str, action_type: str, description: str, details: dict = None):
    """Записать событие в ленту сценариев. Вызывается из других роутеров."""
    log = models.ScenarioLog(
        player_id=player_id,
        action_type=action_type,
        description=description,
        details=json.dumps(details) if details else None
    )
    db.add(log)
    # Не коммитим — это сделает вызывающий код
