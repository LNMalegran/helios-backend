# backend/seed_omsk.py
"""
Скрипт для наполнения БД контентом по Омску.
Запуск: python seed_omsk.py
"""
from database import SessionLocal
from models import (
    Item, PointOfInterest, District, Scenario
)
from datetime import datetime, timezone


def seed():
    db = SessionLocal()
    
    try:
        # === РАСШИРЯЕМ ДИСТРИКТ (весь Омск) ===
        omsk = db.query(District).filter(District.id == 1).first()
        if omsk:
            omsk.name = "Город Омск"
            omsk.min_lat = 54.9000
            omsk.max_lat = 55.0500
            omsk.min_lng = 73.2000
            omsk.max_lng = 73.5000
            db.commit()
        
        # === ПРЕДМЕТЫ ===
        items_data = [
            (1, "Армейский сухпаёк", "Восстанавливает 30 выносливости (FP)", "consumable", "common"),
            (2, "Тяжелый бронежилет", "Надежная физическая защита бронепластинами", "armor", "rare"),
            (3, "Зашифрованный инфопланшет", "Содержит конфиденциальные логи Зоны", "misc", "epic"),
            (4, "Аптечка первой помощи", "Восстанавливает 50 FP и снимает лёгкие ранения", "consumable", "common"),
            (5, "Тактический шлем", "Защита головы от критических попаданий", "armor", "rare"),
            (6, "Электромагнитный импульс", "Одноразовое устройство для отключения электроники", "consumable", "epic"),
            (7, "Биометрический ключ", "Открывает двери с биометрической защитой", "misc", "rare"),
            (8, "Стимулятор адреналина", "+10 к DX и ST на 1 час", "consumable", "rare"),
            (9, "Лёгкая разгрузка", "Увеличивает переносимый вес на 5 кг", "armor", "common"),
            (10, "Загадочный артефакт", "Предмет неизвестного происхождения. Излучает слабое свечение.", "misc", "legendary"),
        ]
        
        for item_id, name, desc, item_type, rarity in items_data:
            existing = db.query(Item).filter(Item.id == item_id).first()
            if not existing:
                db.add(Item(
                    id=item_id, name=name, description=desc,
                    item_type=item_type, rarity=rarity
                ))
        db.commit()
        
        # === POI ПО ОМСКУ ===
        # Формат: (id, name, lat, lng, skill, difficulty, fp_cost, item_id, poi_type)
        pois_data = [
            # === ЦЕНТР (вокруг администрации) ===
            (1, "Заблокированный армейский терминал", 54.9880, 73.3220, "hacking", -1, 15, 3, "cache"),
            (2, "Старый сейф с механическим замком", 54.9830, 73.3150, "lockpicking", 0, 10, 2, "cache"),
            (3, "Точка сбора разведданных", 54.9920, 73.3280, "scouting", -2, 8, None, "intel"),
            
            # === МЕТРО И ПОДЗЕМКА ===
            (4, "Секретный бункер под метро", 54.9750, 73.3050, "hacking", 1, 20, 6, "cache"),
            (5, "Закрытая станция 'Библиотека'", 54.9800, 73.3380, "scouting", 0, 12, 7, "intel"),
            
            # === НАБЕРЕЖНАЯ И МОСТЫ ===
            (6, "Тайник у моста 60-летия ВЛКСМ", 54.9950, 73.3500, "lockpicking", -1, 8, 4, "cache"),
            (7, "Заброшенный лодочный склад", 54.9650, 73.3200, "scouting", 1, 10, 1, "intel"),
            
            # === ПАРКИ И СКВЕРЫ ===
            (8, "Секретная лаборатория в парке", 54.9780, 73.3450, "hacking", 2, 25, 10, "cache"),
            (9, "Охотничий домик в лесопарке", 54.9450, 73.2950, "scouting", -1, 6, None, "intel"),
            
            # === ТЦ И ОБЩЕСТВЕННЫЕ МЕСТА ===
            (10, "Серверная в торговом центре", 54.9700, 73.3700, "hacking", 0, 18, 3, "cache"),
            (11, "Сейф в кабинете директора", 54.9650, 73.3850, "lockpicking", 2, 15, 5, "cache"),
            
            # === ПРОМЗОНЫ ===
            (12, "Заводская проходная", 54.9350, 73.3800, "scouting", 0, 8, None, "intel"),
            (13, "Химическая лаборатория", 54.9250, 73.4100, "hacking", 3, 30, 6, "cache"),
        ]
        
        for poi_id, name, lat, lng, skill, diff, fp, item_id, poi_type in pois_data:
            existing = db.query(PointOfInterest).filter(PointOfInterest.id == poi_id).first()
            if not existing:
                db.add(PointOfInterest(
                    id=poi_id, name=name, lat=lat, lng=lng,
                    poi_type=poi_type, item_id=item_id, is_looted=False,
                    required_skill=skill, difficulty_modifier=diff,
                    stamina_cost=fp
                ))
        db.commit()
        
        # === СЦЕНАРИИ ===
        scenarios_data = [
            {
                "id": "scen_intro",
                "title": "Первый контакт",
                "description": "Изучите основы выживания в Зоне. Взломайте армейский терминал, чтобы получить доступ к координатам других оперативников.",
                "type": "main",
                "difficulty": 8,
                "reward": 200,
                "poi_id": 1
            },
            {
                "id": "scen_supply",
                "title": "Поиск припасов",
                "description": "Зона отрезана от снабжения. Найдите 3 тайника с припасами в разных районах города, чтобы обеспечить выживание команды.",
                "type": "side",
                "difficulty": 10,
                "reward": 300,
                "poi_id": None
            },
            {
                "id": "scen_metro",
                "title": "Тайны метрополитена",
                "description": "Подземные станции скрывают древние секреты. Проберитесь в секретный бункер под метро и узнайте правду о Зоне.",
                "type": "main",
                "difficulty": 12,
                "reward": 500,
                "poi_id": 4
            },
            {
                "id": "scen_hunt",
                "title": "Охота на артефакт",
                "description": "Слухи ходят о загадочном артефакте, спрятанном в подземной лаборатории парка. Доберитесь первыми.",
                "type": "side",
                "difficulty": 14,
                "reward": 700,
                "poi_id": 8
            },
            {
                "id": "scen_recon",
                "title": "Разведка боем",
                "description": "Проведите разведку 5 точек интереса в разных районах Омска. Соберите информацию для командования.",
                "type": "admin",
                "difficulty": 9,
                "reward": 400,
                "poi_id": None
            },
        ]
        
        for scen in scenarios_data:
            existing = db.query(Scenario).filter(Scenario.id == scen["id"]).first()
            if not existing:
                db.add(Scenario(
                    id=scen["id"],
                    title=scen["title"],
                    description=scen["description"],
                    scenario_type=scen["type"],
                    difficulty=scen["difficulty"],
                    reward_coins=scen["reward"],
                    poi_id=scen["poi_id"],
                    status="active",
                    created_by="player_creator",
                    created_at=datetime.now(timezone.utc)
                ))
        db.commit()
        
        print(f"[OK] Засеяно:")
        print(f"   • {len(items_data)} предметов")
        print(f"   • {len(pois_data)} POI по Омску")
        print(f"   • {len(scenarios_data)} сценариев")
        print(f"\n[WORLD] Город Омск готов к игре!")
        
    except Exception as e:
        print(f"[ERR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
