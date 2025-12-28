from datetime import timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..models.user import User
from ..schemas.user import UserCreate, UserResponse
from ..utils.security import get_password_hash, verify_password, create_access_token, authenticate_user
from ..utils.exceptions import AuthenticationError, DatabaseError


class AuthService:
    """Service for user authentication and management."""

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if user already exists
        existing_user = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_user.scalar_one_or_none():
            raise AuthenticationError("User with this email already exists")

        existing_username = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing_username.scalar_one_or_none():
            raise AuthenticationError("Username already taken")

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=hashed_password
        )

        try:
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
            return db_user
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Failed to create user: {str(e)}")

    @staticmethod
    async def register_user(db: AsyncSession, user_data: UserCreate) -> tuple[User, str]:
        """Create a new user and return access token."""
        # Create the user
        user = await AuthService.create_user(db, user_data)

        # Generate access token for the new user
        access_token_expires = timedelta(days=settings.access_token_expire_days)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )

        return user, access_token

    @staticmethod
    async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
        """Authenticate user and return access token."""
        user = await authenticate_user(db, email, password)
        if not user:
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        access_token_expires = timedelta(days=settings.access_token_expire_days)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )

        return user, access_token

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            return await db.get(User, user_id)
        except Exception as e:
            raise DatabaseError(f"Failed to get user: {str(e)}")

    @staticmethod
    async def update_user(db: AsyncSession, user_id: int, **kwargs) -> Optional[User]:
        """Update user information."""
        try:
            user = await db.get(User, user_id)
            if not user:
                return None

            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Failed to update user: {str(e)}")

    @staticmethod
    def user_to_response(user: User) -> UserResponse:
        """Convert User model to UserResponse schema."""
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            created_at=user.created_at
        )