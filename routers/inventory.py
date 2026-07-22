# routers/inventory.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, security
from database import get_db

router = APIRouter(prefix="/inventory", tags=["Инвентарь и Экипировка"])

@router.get("/me")
async def get_inventory(current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    inv = db.query(models.Inventory).filter(models.Inventory.player_id == current_user.id).all()
    return [{
        "item_id": i.item_id, 
        "name": i.item.name, 
        "quantity": i.quantity, 
        "type": i.item.item_type, 
        "rarity": i.item.rarity,
        "is_equipped": current_user.equipped_armor_id == i.item_id
    } for i in inv]

@router.post("/use")
async def use_item(req: schemas.UseItemRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    entry = db.query(models.Inventory).filter(models.Inventory.player_id == current_user.id, models.Inventory.item_id == req.item_id).first()
    if not entry or entry.quantity <= 0:
        raise HTTPException(status_code=404, detail="Предмет отсутствует в инвентаре")
    
    if entry.item.id == 1:  # Сухпаёк
        if current_user.stamina >= 100: 
            raise HTTPException(status_code=400, detail="Выносливость оперативника уже на пределе")
        current_user.stamina = min(100.0, current_user.stamina + 30.0)
        entry.quantity -= 1
        if entry.quantity == 0: 
            db.delete(entry)
        db.commit()
        return {"status": "success", "message": "Использован сухпаёк. Восстановлено 30 FP.", "stamina": current_user.stamina}
        
    raise HTTPException(status_code=400, detail="Этот объект нельзя применить как расходуемый")

@router.post("/equip")
async def equip_item(req: schemas.EquipRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    entry = db.query(models.Inventory).filter(models.Inventory.player_id == current_user.id, models.Inventory.item_id == req.item_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="У вас нет этого снаряжения")
        
    if entry.item.item_type != "armor":
        raise HTTPException(status_code=400, detail="Этот предмет не является экипировкой")

    current_user.equipped_armor_id = entry.item.id
    db.commit()
    return {"status": "success", "message": f"Вы экипировали: {entry.item.name}"}

@router.post("/unequip")
async def unequip_item(req: schemas.EquipRequest, current_user: models.Player = Depends(security.get_current_user), db: Session = Depends(get_db)):
    if current_user.equipped_armor_id != req.item_id:
        raise HTTPException(status_code=400, detail="Данный предмет не надет на персонажа")
        
    current_user.equipped_armor_id = None
    db.commit()
    return {"status": "success", "message": "Снаряжение снято"}
