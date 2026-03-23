from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    token = credentials.credentials
    user_id = AuthService.decode_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str | None:
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        return AuthService.decode_token(token)
    except Exception:
        return None
