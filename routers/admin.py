# backend/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, security
from database import get_db

router = APIRouter(prefix="/admin", tags=["Админ"])


@router.get("/players")
async def list_all_players(
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Все игроки с координатами в реальном времени."""
    players = db.query(models.Player).all()
    return [{
        "player_id": p.id,
        "username": p.username,
        "role": p.role,
        "status": p.status,
        "stamina": round(p.stamina, 1),
        "coordinates": [p.lat, p.lng],
        "is_online": p.status != "idle" or p.last_stamina_update is not None,
        "attributes": {"ST": p.st, "DX": p.dx, "IQ": p.iq, "HT": p.ht}
    } for p in players]


@router.get("/constellations")
async def list_all_constellations(
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Все созвездия в системе."""
    consts = db.query(models.Constellation).all()
    return [{
        "constellation_id": c.id,
        "player_id": c.player_id,
        "name": c.name,
        "title": c.title,
        "influence": c.influence,
        "scenarios_watched": c.scenarios_watched,
        "player_username": c.player.username if c.player else "?"
    } for c in consts]


@router.get("/scenarios")
async def list_all_scenarios(
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Все сценарии с участниками."""
    scenarios = db.query(models.Scenario).all()
    return [{
        "scenario_id": s.id,
        "title": s.title,
        "description": s.description,
        "scenario_type": s.scenario_type,
        "status": s.status,
        "difficulty": s.difficulty,
        "reward_coins": s.reward_coins,
        "poi_id": s.poi_id,
        "participants": [{
            "player_id": sp.player_id,
            "username": db.query(models.Player).filter(models.Player.id == sp.player_id).first().username,
            "progress": sp.progress,
            "status": sp.status
        } for sp in s.participants]
    } for s in scenarios]


@router.post("/scenarios")
async def create_scenario(
    req: schemas.ScenarioCreateRequest,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Создать новый сценарий (только админ)."""
    import uuid
    scenario = models.Scenario(
        id=f"scen_{uuid.uuid4().hex[:12]}",
        title=req.title,
        description=req.description,
        scenario_type=req.scenario_type,
        difficulty=req.difficulty,
        reward_coins=req.reward_coins,
        poi_id=req.poi_id,
        created_by=admin.id,
        status="active"
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "status": "created"
    }


@router.post("/scenarios/{scenario_id}/join")
async def force_join_scenario(
    scenario_id: str,
    player_id: str,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Принудительно добавить игрока в сценарий (только админ)."""
    scenario = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден")
    
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    
    # Проверка, не участвует ли уже
    existing = db.query(models.ScenarioParticipant).filter(
        models.ScenarioParticipant.scenario_id == scenario_id,
        models.ScenarioParticipant.player_id == player_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Игрок уже в сценарии")
    
    participant = models.ScenarioParticipant(
        scenario_id=scenario_id,
        player_id=player_id
    )
    db.add(participant)
    db.commit()
    return {"status": "joined", "scenario_id": scenario_id, "player_id": player_id}


@router.delete("/scenarios/{scenario_id}/participants/{player_id}")
async def remove_from_scenario(
    scenario_id: str,
    player_id: str,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Удалить игрока из сценария (только админ)."""
    participant = db.query(models.ScenarioParticipant).filter(
        models.ScenarioParticipant.scenario_id == scenario_id,
        models.ScenarioParticipant.player_id == player_id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")
    db.delete(participant)
    db.commit()
    return {"status": "removed"}


@router.post("/broadcast")
async def admin_broadcast(
    text: str,
    message_type: str = "system",
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Системное послание от админа — увидят все."""
    from routers.ws import manager
    msg = {
        "type": "constellation_message",
        "from": "СИСТЕМА ГЕЛИОС",
        "title": "Директива Создателя",
        "text": text,
        "message_type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat() if 'datetime' in dir() else None
    }
    await manager.broadcast(msg)
    return {"status": "broadcast_sent", "recipients": len(manager.active_connections)}


@router.post("/teleport/{player_id}")
async def force_teleport(
    player_id: str,
    lat: float,
    lng: float,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Принудительный телепорт игрока (только админ)."""
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    player.lat = lat
    player.lng = lng
    player.status = "idle"
    player.route_path = None
    player.arrival_time = None
    db.commit()
    return {"status": "teleported", "new_coords": [lat, lng]}


from datetime import datetime, timezone

@router.get("/player/{player_id}/profile")
async def get_player_profile_admin(
    player_id: str,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Получить профиль любого игрока (только админ)."""
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    
    return {
        "player_id": player.id,
        "username": player.username,
        "role": player.role,
        "status": player.status,
        "stamina": round(player.stamina, 1),
        "coordinates": [player.lat, player.lng],
        "is_online": True,
        "attributes": {
            "ST": player.st, "DX": player.dx, 
            "IQ": player.iq, "HT": player.ht
        }
    }


@router.get("/player/{player_id}/inventory")
async def get_player_inventory_admin(
    player_id: str,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Инвентарь любого игрока (только админ)."""
    items = db.query(models.Inventory).filter(models.Inventory.player_id == player_id).all()
    return [{
        "item_id": i.item_id,
        "name": i.item.name,
        "quantity": i.quantity,
        "type": i.item.item_type,
        "rarity": i.item.rarity,
        "is_equipped": i.player.equipped_armor_id == i.item_id if i.player else False
    } for i in items]


@router.get("/player/{player_id}/scenarios")
async def get_player_scenarios_admin(
    player_id: str,
    admin: models.Player = Depends(security.require_admin),
    db: Session = Depends(get_db)
):
    """Сценарии любого игрока (только админ)."""
    participants = db.query(models.ScenarioParticipant).filter(
        models.ScenarioParticipant.player_id == player_id
    ).all()
    
    result = []
    for p in participants:
        scen = db.query(models.Scenario).filter(models.Scenario.id == p.scenario_id).first()
        if scen:
            result.append({
                "scenario_id": scen.id,
                "title": scen.title,
                "status": p.status,
                "progress": p.progress
            })
    return result