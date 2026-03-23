from fastapi import APIRouter, HTTPException, status
from app.models.user import UserCreate, UserLogin, UserResponse, Token
from app.models.database import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        user_id = AuthService.generate_user_id()
        password_hash = AuthService.hash_password(user_data.password)
        
        cursor.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, user_data.email, password_hash)
        )
        
        return UserResponse(
            id=user_id,
            email=user_data.email
        )

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (user_data.email,)
        )
        user = cursor.fetchone()
        
        if not user or not AuthService.verify_password(user_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        access_token = AuthService.create_access_token(user["id"])
        
        return Token(access_token=access_token)

@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str):
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=user["id"],
            email=user["email"],
            created_at=user["created_at"]
        )
