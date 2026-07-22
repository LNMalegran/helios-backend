# backend/routers/scenarios.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, security
from database import get_db

router = APIRouter(prefix="/scenarios", tags=["Сценарии"])

@router.get("/mine")
async def get_my_scenarios(
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Сценарии, в которых участвует текущий игрок."""
    participants = db.query(models.ScenarioParticipant).filter(
        models.ScenarioParticipant.player_id == current_user.id
    ).all()
    
    result = []
    for p in participants:
        scenario = db.query(models.Scenario).filter(
            models.Scenario.id == p.scenario_id
        ).first()
        if scenario:
            result.append({
                "scenario_id": scenario.id,
                "title": scenario.title,
                "description": scenario.description,
                "status": p.status,
                "progress": p.progress,
                "scenario_type": scenario.scenario_type,
                "difficulty": scenario.difficulty,
                "reward_coins": scenario.reward_coins
            })
    
    return result

@router.post("/{scenario_id}/join")
async def join_scenario(
    scenario_id: str,
    current_user: models.Player = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Вступить в сценарий."""
    scenario = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден")
    
    existing = db.query(models.ScenarioParticipant).filter(
        models.ScenarioParticipant.scenario_id == scenario_id,
        models.ScenarioParticipant.player_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Вы уже в этом сценарии")
    
    participant = models.ScenarioParticipant(
        scenario_id=scenario_id,
        player_id=current_user.id
    )
    db.add(participant)
    db.commit()
    return {"status": "joined", "scenario_id": scenario_id}
