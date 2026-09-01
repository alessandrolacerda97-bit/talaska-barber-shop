from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .core.config import get_settings
pwd_context=CryptContext(schemes=["bcrypt"],deprecated="auto"); bearer=HTTPBearer()
def hash_password(p): return pwd_context.hash(p)
def verify_password(p,h): return pwd_context.verify(p,h)
def create_token(user): return jwt.encode({"sub":str(user.id),"exp":datetime.now(timezone.utc)+timedelta(hours=12)},get_settings().secret_key,algorithm="HS256")
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    try: uid=int(jwt.decode(credentials.credentials,get_settings().secret_key,algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"Sessão inválida ou expirada.")
    user=db.get(User,uid)
    if not user or not user.active: raise HTTPException(401,"Acesso não autorizado.")
    return user
