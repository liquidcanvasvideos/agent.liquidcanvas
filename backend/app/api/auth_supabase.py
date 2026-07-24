"""
Supabase Authentication API endpoints
Replaces custom JWT auth with Supabase Auth
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    logger.warning("Supabase credentials not configured. Auth will not work.")
    supabase: Optional[Client] = None
else:
    # Use service role key for backend operations (bypasses RLS)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


class Token(BaseModel):
    access_token: str
    token_type: str
    user: Optional[dict] = None


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup", response_model=Token)
async def signup(request: SignUpRequest):
    """
    Sign up a new user with Supabase Auth
    """
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    try:
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password
        })
        
        if response.user:
            return {
                "access_token": response.session.access_token if response.session else "",
                "token_type": "bearer",
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to create user"
            )
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Signup failed: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    """
    Login endpoint - uses Supabase Auth
    Returns Supabase JWT token
    """
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if response.user and response.session:
            return {
                "access_token": response.session.access_token,
                "token_type": "bearer",
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                }
            }
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Get current user from Supabase JWT token - requires authentication
    
    Returns user ID (UUID string)
    """
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify token with Supabase
        token = credentials.credentials
        user_response = supabase.auth.get_user(token)
        
        if user_response.user:
            return user_response.user.id
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        logger.error(f"Auth verification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Get current user from Supabase JWT token - optional authentication
    Returns user ID if authenticated, None otherwise
    """
    if not supabase:
        return None
    
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user_response = supabase.auth.get_user(token)
        
        if user_response.user:
            return user_response.user.id
        else:
            return None
    except Exception:
        # Invalid token - return None instead of raising (for optional auth)
        return None


@router.post("/logout")
async def logout(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Logout endpoint - invalidates Supabase session
    """
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    if credentials:
        try:
            # Supabase handles logout via client-side session management
            # For backend, we just return success
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {e}", exc_info=True)
    
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    """
    Get current user information
    """
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    try:
        user_response = supabase.auth.admin.get_user_by_id(user_id)
        if user_response.user:
            return {
                "id": user_response.user.id,
                "email": user_response.user.email,
                "created_at": user_response.user.created_at
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
    except Exception as e:
        logger.error(f"Get user error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get user information"
        )

