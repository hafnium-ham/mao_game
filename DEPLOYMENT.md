# Mao Game Deployment Guide

## Deployment Options

### Option 1: Self-Hosted on Raspberry Pi (Recommended)

This is the simplest approach - run the server directly on your Pi.

**Steps:**
```bash
# SSH into your Pi
ssh pi@your-pi-ip

# Clone/copy the mao_game folder
cd ~/projects
# Copy the mao_game folder here

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install aiohttp bcrypt

# Run the server
make web PORT=8080
# or: python -m mao_game server --web --port 8080
```

**Access via:**
- Local network: `http://your-pi-ip:8080`
- Tailscale: `http://your-tailscale-pi-ip:8080`

### Option 2: GitHub Pages + External Server

GitHub Pages can ONLY serve static files. For the WebSocket server, you need a separate backend.

**Architecture:**
```
[GitHub Pages]          [Your Server]
    static/        ←→   WebSocket server
   index.html           websocket_server.py
   client.js            :8080
   style.css
```

**Steps:**

1. **Deploy Static Files to GitHub Pages:**
```bash
# Create gh-pages branch
cd mao_game
git checkout -b gh-pages

# Push only static files
git push origin gh-pages

# Enable GitHub Pages in repo settings
# Set source to gh-pages branch
```

2. **Update client.js WebSocket URL:**
```javascript
// In client.js, change the WebSocket connection:
const wsUrl = `wss://your-server.com/ws`;
// Or detect environment:
const wsUrl = window.location.hostname === 'localhost'
    ? `ws://localhost:8080/ws`
    : `wss://your-server.com/ws`;
```

3. **Run WebSocket Server:**
- On your Pi, VPS, or any server with public IP
- Use HTTPS/WSS with proper SSL certificates

### Option 3: Tailscale for Secure Access

Use Tailscale to securely access your Pi from anywhere.

**Steps:**
1. Install Tailscale on Pi: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Install Tailscale on your devices
3. Access via Tailscale IP: `http://100.x.y.z:8080`

**With Tailscale Funnel (public access):**
```bash
# On your Pi
tailscale funnel 8080
# This gives you a public URL like: https://your-name.ts.net
```

## Docker Deployment

A Dockerfile and docker-compose.yml are included.

```bash
# Build and run with Docker
docker-compose up -d

# Or build manually
docker build -t mao-game .
docker run -p 8080:8080 mao-game
```

## Testing

Run the test suite:
```bash
make test
# or: python -m pytest tests/ -v
```

## Linting

Add a linter for code quality:
```bash
# Install flake8
pip install flake8

# Run linter
flake8 mao_game/ --max-line-length=100 --ignore=E501,W503
```

## Assets Needed

The game currently uses text-based card rendering. To improve:

1. **Card Images** - Already in `static/cards/` (SVG/PNG playing cards)
2. **Logo** - `mao.jpeg` exists, could be used for branding
3. **Favicon** - Create a favicon.ico
4. **Background** - Optional texture/pattern for theme

## RESTful API Explanation

The current architecture uses WebSocket for real-time communication. A RESTful API would add:

**Benefits:**
- HTTP endpoints for queries (GET /api/lobbies)
- Easier debugging with curl/Postman
- Polling fallback for clients without WebSocket

**Example Endpoints:**
```
GET  /api/lobbies           # List lobbies
POST /api/lobbies           # Create lobby
GET  /api/lobbies/{code}    # Get lobby info
POST /api/lobbies/{code}/join   # Join lobby

# Game actions via WebSocket for real-time
ws://server/ws?lobby=CODE   # WebSocket connection
```

**Implementation:**
Add HTTP route handlers alongside WebSocket in `websocket_server.py`:
```python
async def _serve_lobbies_api(self, request):
    lobbies = self.lobby_manager.list_lobbies()
    return web.json_response({"lobbies": lobbies})
```

## Project Structure

```
mao_game/
├── __init__.py
├── __main__.py           # Entry point
├── main.py               # CLI handler
├── Makefile              # Build/test commands
├── requirements.txt      # Python dependencies
├── config/
│   ├── settings.py      # Game configuration
│   └── rules.json       # Rule definitions
├── core/
│   ├── card.py          # Card class
│   ├── deck.py          # Deck class
│   ├── game.py          # Game state logic
│   └── player.py        # Player class
├── network/
│   ├── lobby_manager.py # Multi-lobby support
│   ├── protocol.py      # Message types
│   └── websocket_server.py  # Main server
├── static/
│   ├── index.html       # Main page
│   ├── client.js        # Frontend logic
│   ├── style.css        # Styling
│   └── cards/           # Card images
└── tests/
    ├── test_*.py        # Unit tests
    └── ...
```

## Quick Start

```bash
# From project root
cd /Users/hathsin/Desktop/claude_test/mao_game

# Install dependencies
make install

# Run tests
make test

# Start web server
make web

# Open browser
open http://localhost:8080
```