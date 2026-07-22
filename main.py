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

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        # === Создаём таблицы (если ещё нет) ===
        models.Base.metadata.create_all(bind=engine)
        
        # === Сидирование с обработкой ошибок ===
        try:
            if not db.query(models.District).filter(models.District.id == 1).first():
                db.add(models.District(
                    id=1, name="Город Омск",
                    min_lat=54.9000, max_lat=55.0500,
                    min_lng=73.2000, max_lng=73.5000
                ))
                db.commit()
        except Exception as e:
            print(f"District seed error: {e}")
            db.rollback()
        
        try:
            if not db.query(models.Item).filter(models.Item.id == 1).first():
                items = [
                    (1, "Армейский сухпаёк", "Восстанавливает 30 FP", "consumable", "common"),
                    (2, "Тяжелый бронежилет", "Физическая защита", "armor", "rare"),
                    (3, "Зашифрованный инфопланшет", "Содержит логи", "misc", "epic"),
                    (4, "Аптечка", "Восстанавливает 50 FP", "consumable", "common"),
                    (5, "Тактический шлем", "Защита головы", "armor", "rare"),
                    (6, "ЭМИ", "Отключает электронику", "consumable", "epic"),
                    (7, "Биометрический ключ", "Открывает двери", "misc", "rare"),
                    (8, "Стимулятор", "+10 к DX и ST", "consumable", "rare"),
                    (9, "Лёгкая разгрузка", "+5 кг веса", "armor", "common"),
                    (10, "Загадочный артефакт", "Светится", "misc", "legendary"),
                ]
                for item_id, name, desc, item_type, rarity in items:
                    db.add(models.Item(id=item_id, name=name, description=desc, item_type=item_type, rarity=rarity))
                db.commit()
        except Exception as e:
            print(f"Items seed error: {e}")
            db.rollback()
        
        # Игрок kirill
        try:
            if not db.query(models.Player).filter(models.Player.username == "kirill").first():
                db.add(models.Player(
                    id="player_kirill", username="kirill",
                    password_hash=hash_password("12345"),
                    role="incarnation", stamina=100.0,
                    lat=54.9884, lng=73.3242,
                    current_district_id=1, status="idle",
                    last_stamina_update=datetime.now(timezone.utc),
                    st=10, dx=11, iq=13, ht=11,
                    skill_hacking=14
                ))
                db.commit()
        except Exception as e:
            print(f"Player kirill seed error: {e}")
            db.rollback()
        
        # Игрок creator (твой аккаунт админа)
        try:
            if not db.query(models.Player).filter(models.Player.username == "creator").first():
                db.add(models.Player(
                    id="player_creator", username="creator",
                    password_hash=hash_password("789"),
                    role="admin", stamina=100.0,
                    lat=54.9884, lng=73.3242,
                    current_district_id=1, status="idle",
                    last_stamina_update=datetime.now(timezone.utc),
                    st=15, dx=15, iq=15, ht=15,
                    skill_hacking=20, skill_lockpicking=20, skill_scouting=20
                ))
                db.commit()
        except Exception as e:
            print(f"Player creator seed error: {e}")
            db.rollback()
        
        # POI
        try:
            existing_poi_count = db.query(models.PointOfInterest).count()
            if existing_poi_count == 0:
                pois = [
                    (1, "Заблокированный армейский терминал", 54.9880, 73.3220, "hacking", -1, 15, 3, "cache"),
                    (2, "Старый сейф", 54.9830, 73.3150, "lockpicking", 0, 10, 2, "cache"),
                    (3, "Точка разведданных", 54.9920, 73.3280, "scouting", -2, 8, None, "intel"),
                    (4, "Бункер под метро", 54.9750, 73.3050, "hacking", 1, 20, 6, "cache"),
                    (5, "Станция 'Библиотека'", 54.9800, 73.3380, "scouting", 0, 12, 7, "intel"),
                    (6, "Тайник у моста", 54.9950, 73.3500, "lockpicking", -1, 8, 4, "cache"),
                    (7, "Лодочный склад", 54.9650, 73.3200, "scouting", 1, 10, 1, "intel"),
                    (8, "Лаборатория в парке", 54.9780, 73.3450, "hacking", 2, 25, 10, "cache"),
                    (9, "Охотничий домик", 54.9450, 73.2950, "scouting", -1, 6, None, "intel"),
                    (10, "Серверная в ТЦ", 54.9700, 73.3700, "hacking", 0, 18, 3, "cache"),
                    (11, "Сейф директора", 54.9650, 73.3850, "lockpicking", 2, 15, 5, "cache"),
                    (12, "Заводская проходная", 54.9350, 73.3800, "scouting", 0, 8, None, "intel"),
                    (13, "Хим. лаборатория", 54.9250, 73.4100, "hacking", 3, 30, 6, "cache"),
                ]
                for poi_id, name, lat, lng, skill, diff, fp, item_id, poi_type in pois:
                    db.add(models.PointOfInterest(
                        id=poi_id, name=name, lat=lat, lng=lng,
                        poi_type=poi_type, item_id=item_id,
                        is_looted=False, required_skill=skill,
                        difficulty_modifier=diff, stamina_cost=fp
                    ))
                db.commit()
        except Exception as e:
            print(f"POI seed error: {e}")
            db.rollback()
        
        # Сценарии
        try:
            existing_scen_count = db.query(models.Scenario).count()
            if existing_scen_count == 0:
                scenarios = [
                    {"id": "scen_intro", "title": "Первый контакт", "description": "Изучите основы выживания в Зоне", "type": "main", "diff": 8, "reward": 200, "poi": 1},
                    {"id": "scen_supply", "title": "Поиск припасов", "description": "Найдите 3 тайника с припасами", "type": "side", "diff": 10, "reward": 300, "poi": None},
                    {"id": "scen_metro", "title": "Тайны метрополитена", "description": "Проберитесь в секретный бункер", "type": "main", "diff": 12, "reward": 500, "poi": 4},
                    {"id": "scen_hunt", "title": "Охота на артефакт", "description": "Доберитесь до артефакта первыми", "type": "side", "diff": 14, "reward": 700, "poi": 8},
                    {"id": "scen_recon", "title": "Разведка боем", "description": "Проведите разведку 5 точек", "type": "admin", "diff": 9, "reward": 400, "poi": None},
                ]
                for s in scenarios:
                    db.add(models.Scenario(
                        id=s["id"], title=s["title"], description=s["description"],
                        scenario_type=s["type"], difficulty=s["diff"],
                        reward_coins=s["reward"], poi_id=s["poi"],
                        status="active", created_by="player_creator",
                        created_at=datetime.now(timezone.utc)
                    ))
                db.commit()
        except Exception as e:
            print(f"Scenarios seed error: {e}")
            db.rollback()
        
        # Запускаем WebSocket фоновую задачу
        asyncio.create_task(ws_router.push_status_updates())
        
        print("[OK] БД инициализирована")
        
    except Exception as e:
        print(f"[ERR] Lifespan error: {e}")
    finally:
        db.close()
    
    yield



# === Создаём приложение ===
app = FastAPI(lifespan=lifespan, title="Гелиос - Командное Ядро Бэкенда")

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://gelios-tau.vercel.app"],
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
