# Mao Game Architecture

## Overview

Mao is a multiplayer card game with a WebSocket-based real-time server. Players can join lobbies, play games, and optionally create accounts for persistent profiles.

## Backend Components

### 1. WebSocket Server (`network/websocket_server.py`)

The main server using **aiohttp** for async WebSocket handling:

- **Port**: 8080 (web mode) or 5555 (CLI mode)
- **Protocol**: WebSocket with JSON messages
- **Features**:
  - Multi-lobby support (multiple concurrent games)
  - Password-protected lobbies with bcrypt hashing
  - Real-time game state broadcasting
  - Point of Order (POO) voting system
  - Mao declaration with challenge window

### 2. Game Logic (`core/game.py`)

State machine managing:
- Game phases: WAITING, IN_PROGRESS, POINT_OF_ORDER, GAME_OVER
- Turn management with direction (clockwise/counter-clockwise)
- Card playing rules (delegated to players)
- Penalty tracking and voting
- Mao declaration system

### 3. Database (`database/`)

**SQLite** for simplicity - single file, no server needed.

#### Tables

**users**
```sql
id INTEGER PRIMARY KEY
username TEXT UNIQUE
password_hash TEXT  -- bcrypt
display_name TEXT
avatar TEXT         -- base64 image
created_at TIMESTAMP
last_login TIMESTAMP
```

**game_history** (for future stats)
```sql
id INTEGER PRIMARY KEY
user_id INTEGER
game_code TEXT
won BOOLEAN
cards_played INTEGER
penalties_given INTEGER
penalties_received INTEGER
played_at TIMESTAMP
```

#### Auth Functions (`database/auth.py`)

- `create_user(username, password, display_name)` - Register new user
- `authenticate_user(username, password)` - Login, returns user dict
- `get_user(user_id)` - Get user by ID
- `update_user_avatar(user_id, avatar)` - Save avatar to account

### 4. Message Protocol (`network/protocol.py`)

All messages are JSON with structure:
```json
{
  "type": "message_type",
  "player_id": "optional_sender_id",
  "data": { ... }
}
```

**Key Message Types**:
- `connect`, `login`, `register` - Authentication
- `join_lobby`, `create_lobby`, `leave_lobby` - Lobby management
- `play_card`, `draw_card`, `knock` - Game actions
- `give_penalty`, `vote_penalty`, `vote` - Penalty system
- `point_of_order`, `end_point_of_order` - POO system
- `game_state`, `hand_update` - State sync

## Data Storage

| Data | Storage | Persistence |
|------|---------|-------------|
| User accounts | SQLite (`config/mao_game.db`) | Persistent |
| Game state | Memory | Lost on restart |
| Lobby metadata | JSON (`config/lobbies.json`) | Persistent |
| Player sessions | Memory | Connection-based |

## Security

- **Passwords**: Hashed with bcrypt
- **Lobby passwords**: bcrypt or SHA256 fallback
- **No HTTPS**: Run behind reverse proxy (nginx, Tailscale)
- **Session**: No tokens - WebSocket connection is the session

## Deployment

See `DEPLOYMENT.md` for deployment options:
1. Self-hosted on Raspberry Pi
2. GitHub Pages + WebSocket server
3. Tailscale for secure access