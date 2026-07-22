# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio

import models
from database import SessionLocal, engine
from security import hash_password
from config import settings
from routers import auth, character, inventory, poi, ws as ws_router, constellation, admin, scenarios

# Создаём таблицы при старте
models.Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://your-app.vercel.app",  # ← ДОБАВЬ ПОСЛЕ ДЕПЛОЯ
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация БД и фоновых задач при старте."""
    db = SessionLocal()
    
    # === Сидирование данных ===
    if not db.query(models.District).filter(models.District.id == 1).first():
        db.add(models.District(
            id=1, 
            name="Стартовая зона (Омск)", 
            min_lat=54.9500, max_lat=55.0500, 
            min_lng=73.2500, max_lng=73.4500
        ))
    
    if not db.query(models.Item).filter(models.Item.id == 1).first():
        db.add(models.Item(
            id=1, 
            name="Армейский сухпаёк", 
            description="Восстанавливает 30 выносливости (FP)", 
            item_type="consumable", 
            rarity="common"
        ))
    if not db.query(models.Item).filter(models.Item.id == 2).first():
        db.add(models.Item(
            id=2, 
            name="Тяжелый бронежилет", 
            description="Надежная физическая защита бронепластинами", 
            item_type="armor", 
            rarity="rare"
        ))
    if not db.query(models.Item).filter(models.Item.id == 3).first():
        db.add(models.Item(
            id=3, 
            name="Зашифрованный инфопланшет", 
            description="Содержит конфиденциальные логи Зоны", 
            item_type="misc", 
            rarity="epic"
        ))

    if not db.query(models.Player).filter(models.Player.username == "kirill").first():
        db.add(models.Player(
            id="player_kirill", 
            username="kirill", 
            password_hash=hash_password("12345"),
            stamina=100.0, 
            current_district_id=1,
            lat=54.9884,
            lng=73.3242,
            status="idle",
            last_stamina_update=datetime.now(timezone.utc),
            st=10, dx=11, iq=13, ht=11,
            skill_hacking=14, skill_lockpicking=0, skill_scouting=0
        ))

    if not db.query(models.Player).filter(models.Player.username == "creator").first():
        db.add(models.Player(
            id="player_creator",
            username="Reader",
            password_hash=hash_password("789"),  # Смени на свой пароль!
            stamina=100.0,
            current_district_id=1,
            lat=54.9884,
            lng=73.3242,
            status="idle",
            last_stamina_update=datetime.now(timezone.utc),
            role="admin",  # <-- ВАЖНО
            st=15, dx=15, iq=15, ht=15,
            skill_hacking=20, skill_lockpicking=20, skill_scouting=20
    ))

    if not db.query(models.PointOfInterest).filter(models.PointOfInterest.id == 1).first():
        db.add(models.PointOfInterest(
            id=1, 
            name="Заблокированный армейский терминал", 
            lat=54.9880, lng=73.3220, 
            poi_type="cache", 
            item_id=3, 
            is_looted=False, 
            required_skill="hacking", 
            difficulty_modifier=-1, 
            stamina_cost=15
        ))
    if not db.query(models.PointOfInterest).filter(models.PointOfInterest.id == 2).first():
        db.add(models.PointOfInterest(
            id=2, 
            name="Старый сейф с механическим замком", 
            lat=54.9830, lng=73.3150, 
            poi_type="cache", 
            item_id=2, 
            is_looted=False, 
            required_skill="lockpicking", 
            difficulty_modifier=0, 
            stamina_cost=10
        ))

    db.commit()
    db.close()
    
    # === Запуск фоновой задачи WebSocket ===
    asyncio.create_task(ws_router.push_status_updates())
    
    yield


# === Создаём приложение ===
app = FastAPI(lifespan=lifespan, title="Гелиос - Командное Ядро Бэкенда")

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Подключаем роутеры (ПОСЛЕ создания app) ===
app.include_router(auth.router)
app.include_router(character.router)
app.include_router(inventory.router)
app.include_router(poi.router)
app.include_router(ws_router.router)
app.include_router(constellation.router)
app.include_router(admin.router)
app.include_router(scenarios.router)
