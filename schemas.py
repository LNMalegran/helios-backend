# backend/schemas.py
from pydantic import BaseModel
from typing import List, Optional

class UserRegister(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class MoveRequest(BaseModel):
    target_lat: float
    target_lng: float

class RestRequest(BaseModel):
    hours: int

class UseItemRequest(BaseModel):
    item_id: int

class EquipRequest(BaseModel):
    item_id: int

class LootPOIRequest(BaseModel):
    poi_id: int

class ConstellationMessageRequest(BaseModel):
    text: str
    message_type: str = "whisper"  # whisper, indirect_message, blessing, warning
    target_player_id: Optional[str] = None

class ConstellationPromoteRequest(BaseModel):
    name: str
    title: str

class ConstellationPromoteRequest(BaseModel):
    name: str
    title: str

class ScenarioCreateRequest(BaseModel):
    title: str
    description: str
    scenario_type: str = "main"
    difficulty: int = 10
    reward_coins: int = 100
    poi_id: Optional[int] = None

class ScenarioJoinResponse(BaseModel):
    scenario_id: str
    status: str
    progress: int