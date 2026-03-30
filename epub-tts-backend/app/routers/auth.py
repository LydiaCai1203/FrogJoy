from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.exc import IntegrityError
from app.models.user import UserCreate, UserLogin, UserResponse, Token, ThemeIn, ThemeOut
from app.models.database import get_db
from app.models.models import User, UserThemePreferences
from app.services.auth_service import AuthService
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    with get_db() as db:
        try:
            existing = db.query(User).filter(User.email == user_data.email).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            user_id = AuthService.generate_user_id()
            password_hash = AuthService.hash_password(user_data.password)

            user = User(id=user_id, email=user_data.email, password_hash=password_hash)
            db.add(user)
            db.commit()

            return UserResponse(id=user_id, email=user_data.email)
        except HTTPException:
            raise
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        except Exception:
            db.rollback()
            raise

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    with get_db() as db:
        user = db.query(User).filter(User.email == user_data.email).first()

        if not user or not AuthService.verify_password(user_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        access_token = AuthService.create_access_token(user.id)
        return Token(access_token=access_token)

@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )

@router.get("/theme", response_model=ThemeOut)
async def get_theme(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
    if not row:
        return ThemeOut(theme="eye-care")
    return ThemeOut(theme=row.theme)

@router.put("/theme", response_model=ThemeOut)
async def save_theme(theme_data: ThemeIn, user_id: str = Depends(get_current_user)):
    valid_themes = ["day", "night", "eye-care"]
    if theme_data.theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Invalid theme")
    with get_db() as db:
        existing = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
        if existing:
            existing.theme = theme_data.theme
        else:
            existing = UserThemePreferences(user_id=user_id, theme=theme_data.theme)
            db.add(existing)
        db.commit()
    return ThemeOut(theme=theme_data.theme)
