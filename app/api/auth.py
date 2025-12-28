from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.user import UserCreate, UserLogin, UserResponse, Token, UserRegistrationResponse, UserLoginResponse
from ..schemas.common import SuccessResponse, ErrorResponse
from ..services.auth_service import AuthService
from ..utils.security import get_current_user
from ..utils.exceptions import AuthenticationError
from ..models.user import User

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user and return access token.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        UserRegistrationResponse: Created user information and access token
    """
    try:
        user, access_token = await AuthService.register_user(db, user_data)
        return UserRegistrationResponse(
            user=AuthService.user_to_response(user),
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 7  # 7 days in seconds
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.post("/login", response_model=UserLoginResponse)
async def login(
    user_credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return access token with user details.

    Args:
        user_credentials: User login credentials
        db: Database session

    Returns:
        UserLoginResponse: JWT access token and user details
    """
    try:
        user, access_token = await AuthService.login_user(
            db, user_credentials.email, user_credentials.password
        )
        return UserLoginResponse(
            user=AuthService.user_to_response(user),
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 7  # 7 days in seconds
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: User information
    """
    return AuthService.user_to_response(current_user)


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout user (client-side token removal).

    Args:
        current_user: Current authenticated user

    Returns:
        SuccessResponse: Logout confirmation
    """
    return SuccessResponse(
        message="Successfully logged out",
        timestamp=datetime.utcnow()
    )