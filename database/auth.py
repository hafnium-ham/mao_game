"""Authentication functions for user accounts."""
import bcrypt
from .db import get_db


def create_user(username: str, password: str, display_name: str = None) -> dict:
    """
    Create a new user account.

    Args:
        username: Unique username
        password: Plain text password
        display_name: Optional display name (defaults to username)

    Returns:
        User dict with id, username, display_name on success
        None if username already exists
    """
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        with get_db() as conn:
            cursor = conn.execute(
                'INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)',
                (username, password_hash, display_name or username)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return {
                'id': user_id,
                'username': username,
                'display_name': display_name or username
            }
    except sqlite3.IntegrityError:
        # Username already exists
        return None


def authenticate_user(username: str, password: str) -> dict | None:
    """
    Authenticate a user by username and password.

    Args:
        username: Username to authenticate
        password: Plain text password

    Returns:
        User dict on success, None on failure
    """
    with get_db() as conn:
        row = conn.execute(
            'SELECT id, username, password_hash, display_name, avatar FROM users WHERE username = ?',
            (username,)
        ).fetchone()

        if row and bcrypt.checkpw(password.encode('utf-8'), row['password_hash']):
            # Update last_login
            conn.execute(
                'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
                (row['id'],)
            )
            conn.commit()
            return {
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'avatar': row['avatar']
            }

    return None


def get_user(user_id: int) -> dict | None:
    """
    Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User dict or None if not found
    """
    with get_db() as conn:
        row = conn.execute(
            'SELECT id, username, display_name, avatar FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()

        if row:
            return {
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'avatar': row['avatar']
            }

    return None


def get_user_by_username(username: str) -> dict | None:
    """
    Get user by username.

    Args:
        username: Username to look up

    Returns:
        User dict or None if not found
    """
    with get_db() as conn:
        row = conn.execute(
            'SELECT id, username, display_name, avatar FROM users WHERE username = ?',
            (username,)
        ).fetchone()

        if row:
            return {
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'avatar': row['avatar']
            }

    return None


def update_user_avatar(user_id: int, avatar: str) -> bool:
    """
    Update user's avatar.

    Args:
        user_id: User ID
        avatar: Base64 encoded avatar image

    Returns:
        True on success, False on failure
    """
    try:
        with get_db() as conn:
            conn.execute(
                'UPDATE users SET avatar = ? WHERE id = ?',
                (avatar, user_id)
            )
            conn.commit()
        return True
    except Exception:
        return False


def update_user_display_name(user_id: int, display_name: str) -> bool:
    """
    Update user's display name.

    Args:
        user_id: User ID
        display_name: New display name

    Returns:
        True on success, False on failure
    """
    try:
        with get_db() as conn:
            conn.execute(
                'UPDATE users SET display_name = ? WHERE id = ?',
                (display_name, user_id)
            )
            conn.commit()
        return True
    except Exception:
        return False


def record_game(user_id: int, game_code: str, won: bool,
                 cards_played: int = 0, penalties_given: int = 0, penalties_received: int = 0) -> bool:
    """
    Record a game in the user's history.

    Args:
        user_id: User ID
        game_code: Game/lobby code
        won: Whether the user won
        cards_played: Number of cards played
        penalties_given: Number of penalties given
        penalties_received: Number of penalties received

    Returns:
        True on success
    """
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO game_history (user_id, game_code, won, cards_played, penalties_given, penalties_received)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, game_code, won, cards_played, penalties_given, penalties_received))
            conn.commit()
        return True
    except Exception:
        return False


def get_user_stats(user_id: int) -> dict:
    """
    Get user statistics.

    Args:
        user_id: User ID

    Returns:
        Dict with games_played, games_won, win_rate, total_penalties_given, total_penalties_received
    """
    with get_db() as conn:
        row = conn.execute('''
            SELECT
                COUNT(*) as games_played,
                SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as games_won,
                SUM(penalties_given) as total_penalties_given,
                SUM(penalties_received) as total_penalties_received
            FROM game_history
            WHERE user_id = ?
        ''', (user_id,)).fetchone()

        if row:
            games_played = row['games_played'] or 0
            games_won = row['games_won'] or 0
            return {
                'games_played': games_played,
                'games_won': games_won,
                'win_rate': round(games_won / games_played * 100, 1) if games_played > 0 else 0,
                'total_penalties_given': row['total_penalties_given'] or 0,
                'total_penalties_received': row['total_penalties_received'] or 0
            }

    return {
        'games_played': 0,
        'games_won': 0,
        'win_rate': 0,
        'total_penalties_given': 0,
        'total_penalties_received': 0
    }