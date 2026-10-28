from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.config import settings
from backend.db import get_db
from backend.models import User, Role

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(value: str) -> str:
    return pwd_context.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return pwd_context.verify(value, hashed)


def create_token(user: User) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user.username, "role": user.role.value, "exp": expiry}, settings.secret_key, algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        data = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])
        user = db.query(User).filter_by(username=data.get("sub"), active=True).first()
    except JWTError as exc:
        raise HTTPException(401, "Invalid or expired token") from exc
    if not user:
        raise HTTPException(401, "Invalid or inactive account")
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Role is not permitted to perform this action")
        return user
    return checker
