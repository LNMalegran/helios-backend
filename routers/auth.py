# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, schemas, security
from database import get_db

router = APIRouter(tags=["Авторизация"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(models.Player).filter(models.Player.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже зарегистрирован")
    
    new_player = models.Player(
        id=f"player_{user_data.username}",
        username=user_data.username,
        password_hash=security.hash_password(user_data.password),
        stamina=100.0,
        current_district_id=1,
        status="idle",
        st=10, dx=10, iq=10, ht=10
    )
    db.add(new_player)
    db.commit()
    return {"status": "success", "message": "Регистрация успешна!"}

@router.post("/login", response_model=schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.username == form_data.username).first()
    if not player or not security.verify_password(form_data.password, player.password_hash):
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")
    
    access_token = security.create_access_token(data={"sub": player.username})
    return {"access_token": access_token, "token_type": "bearer"}
