# models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone


class District(Base):
    __tablename__ = "districts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    min_lat = Column(Float, nullable=False)
    max_lat = Column(Float, nullable=False)
    min_lng = Column(Float, nullable=False)
    max_lng = Column(Float, nullable=False)


class Player(Base):
    __tablename__ = "players"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    
    # Роль: incarnation, constellation, admin
    role = Column(String, default="incarnation")
    
    stamina = Column(Float, default=100.0)
    lat = Column(Float, default=54.9850)
    lng = Column(Float, default=73.3200)
    current_district_id = Column(Integer, ForeignKey("districts.id"))
    
    # Характеристики GURPS
    st = Column(Integer, default=10)
    dx = Column(Integer, default=10)
    iq = Column(Integer, default=10)
    ht = Column(Integer, default=10)

    # Навыки GURPS
    skill_hacking = Column(Integer, default=0)
    skill_lockpicking = Column(Integer, default=0)
    skill_scouting = Column(Integer, default=0)

    # Состояния игры
    status = Column(String, default="idle")
    last_stamina_update = Column(DateTime, nullable=True)
    
    # Перемещение в реальном времени
    start_time = Column(DateTime, nullable=True)
    arrival_time = Column(DateTime, nullable=True)
    total_duration = Column(Float, default=0.0)
    route_path = Column(String, nullable=True)

    # Экипировка
    equipped_armor_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    
    inventory = relationship("Inventory", cascade="all, delete-orphan")
    equipped_armor = relationship("Item", foreign_keys=[equipped_armor_id])


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    item_type = Column(String, default="misc")
    rarity = Column(String, default="common")


class Inventory(Base):
    __tablename__ = "inventories"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"))
    quantity = Column(Integer, default=1)
    item = relationship("Item")


class PointOfInterest(Base):
    __tablename__ = "points_of_interest"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    poi_type = Column(String, default="cache")
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    is_looted = Column(Boolean, default=False)

    required_skill = Column(String, default="scouting")
    difficulty_modifier = Column(Integer, default=0)
    stamina_cost = Column(Integer, default=10)

    item = relationship("Item")


class Constellation(Base):
    """Созвездие-наблюдатель."""
    __tablename__ = "constellations"
    id = Column(String, primary_key=True, index=True)
    player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"), unique=True)
    name = Column(String, nullable=False)
    title = Column(String, nullable=True)
    influence = Column(Integer, default=0)
    scenarios_watched = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    player = relationship("Player", backref="constellation_profile")


class ConstellationMessage(Base):
    """Сообщения от созвездий к воплощениям."""
    __tablename__ = "constellation_messages"
    id = Column(String, primary_key=True, index=True)
    constellation_id = Column(String, ForeignKey("constellations.id", ondelete="CASCADE"))
    target_player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=True)
    text = Column(String, nullable=False)
    message_type = Column(String, default="whisper")
    influence_cost = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    constellation = relationship("Constellation")


class ScenarioLog(Base):
    """Лог событий сценариев."""
    __tablename__ = "scenario_logs"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"))
    action_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Scenario(Base):
    """Игровой сценарий (квест)."""
    __tablename__ = "scenarios"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    scenario_type = Column(String, default="main")
    status = Column(String, default="active")
    difficulty = Column(Integer, default=10)
    reward_coins = Column(Integer, default=100)
    poi_id = Column(Integer, ForeignKey("points_of_interest.id"), nullable=True)
    created_by = Column(String, ForeignKey("players.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    participants = relationship("ScenarioParticipant", cascade="all, delete-orphan", back_populates="scenario")


class ScenarioParticipant(Base):
    """Участник сценария."""
    __tablename__ = "scenario_participants"
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(String, ForeignKey("scenarios.id", ondelete="CASCADE"))
    player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"))
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    progress = Column(Integer, default=0)
    status = Column(String, default="active")
    
    scenario = relationship("Scenario", back_populates="participants")
