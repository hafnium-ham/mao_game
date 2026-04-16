"""Database module for user accounts and game history."""
from .db import get_db, init_db, close_db
from .auth import create_user, authenticate_user, get_user, update_user_avatar, update_user_display_name