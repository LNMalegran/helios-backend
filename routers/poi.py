# routers/poi.py
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, security
from database import get_db
from routers.constellation import log_event

router = APIRouter(prefix="/poi", tags=["Точки интереса (POI)"])

GURPS_SKILLS_CONFIG = {
    "hacking": {"base_attr": "iq", "default_penalty": -5},
    "lockpicking": {"base_attr": "dx", "default_penalty": -5},
    "scouting": {"base_attr": "iq", "default_penalty": -4}
}

@router.get("/nearby")
async def get_nearby_poi(current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    all_pois = db.query(models.PointOfInterest).filter(models.PointOfInterest.is_looted == False).all()
    nearby = []
    # Радиус обнаружения вокруг игрока
    for poi in all_pois:
        if abs(current_user.lat - poi.lat) <= 0.005 and abs(current_user.lng - poi.lng) <= 0.005:
            nearby.append({
                "poi_id": poi.id, 
                "name": poi.name, 
                "lat": poi.lat,
                "lng": poi.lng,
                "skill_needed": poi.required_skill, 
                "fp_cost": poi.stamina_cost
            })
    return {"visible_pois": nearby}

@router.post("/loot")
async def loot_poi(req: schemas.LootPOIRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    poi = db.query(models.PointOfInterest).filter(models.PointOfInterest.id == req.poi_id).first()
    if not poi: 
        raise HTTPException(status_code=404, detail="Объект исследования потерян")
    if poi.is_looted: 
        raise HTTPException(status_code=400, detail="Этот схрон уже выпотрошен")
    if abs(current_user.lat - poi.lat) > 0.005 or abs(current_user.lng - poi.lng) > 0.005:
        raise HTTPException(status_code=400, detail="Вы слишком далеко для установления физического контакта")

    if current_user.stamina < poi.stamina_cost:
        raise HTTPException(status_code=400, detail=f"Вы слишком измотаны. Требуется {poi.stamina_cost} FP")
    
    current_user.stamina -= poi.stamina_cost

    # Логика кубиков GURPS 3d6
    skill_name = poi.required_skill
    player_trained_skill = getattr(current_user, f"skill_{skill_name}")
    is_using_default = False
    
    if player_trained_skill > 0:
        base_target = player_trained_skill
    else:
        is_using_default = True
        config = GURPS_SKILLS_CONFIG[skill_name]
        associated_attribute_value = getattr(current_user, config["base_attr"])
        base_target = associated_attribute_value + config["default_penalty"]

    effective_target = base_target + poi.difficulty_modifier
    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    total_roll = d1 + d2 + d3
    is_success = total_roll <= effective_target

    if total_roll == 18 or (total_roll == 17 and effective_target <= 15):
        poi.is_looted = True
        db.commit()
        log_event(db, current_user.id, "loot_critical_fail",
              f"{current_user.username} заблокировал {poi.name} навсегда",
              {"poi_id": poi.id, "roll": f"{d1}+{d2}+{d3}={total_roll}"})
        db.commit()
        return {"result": "CRITICAL_FAILURE", "roll": f"{d1}+{d2}+{d3} = {total_roll}", "message": "Критический провал! Защитные системы заблокировали контейнер навсегда."}

    if not is_success:
        db.commit()
        return {"result": "FAILURE", "roll": f"{d1}+{d2}+{d3} = {total_roll}", "target": effective_target, "message": f"Неудача взлома! {'(Штраф за отсутствие навыка)' if is_using_default else ''}"}

    if poi.item_id:
        inv_entry = db.query(models.Inventory).filter(models.Inventory.player_id == current_user.id, models.Inventory.item_id == poi.item_id).first()
        if inv_entry: 
            inv_entry.quantity += 1
        else: 
            db.add(models.Inventory(player_id=current_user.id, item_id=poi.item_id, quantity=1))

    poi.is_looted = True
    db.commit()
    log_event(db, current_user.id, "loot_success",
              f"{current_user.username} вскрыл схрон: {poi.name}",
              {"poi_id": poi.id, "roll": f"{d1}+{d2}+{d3}={total_roll}", "reward": poi.item.name if poi.item else None})
    db.commit()
    return {"result": "SUCCESS", "roll": f"{d1}+{d2}+{d3} = {total_roll}", "reward": poi.item.name if poi.item else "Данные ядра"}
