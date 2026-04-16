# Mao Game Deployment Guide

## Quick Start

```bash
cd mao_game
make install   # Install dependencies
make web       # Start server on port 8080
# Open http://localhost:8080
```

## Database

**SQLite** - single file, no setup required.

- Location: `config/mao_game.db` (created automatically)
- Stores: User accounts, game history
- Backup: Just copy the `.db` file

## Deployment Options

### Option 1: Raspberry Pi + GitHub Pages (Recommended)

Host the static files on GitHub Pages, run the WebSocket server on your Pi.

**Architecture:**
```
[GitHub Pages]              [Raspberry Pi]
  Static files      ←→      WebSocket Server
  index.html                :8080
  client.js                 mao_game.db
  style.css
```

**Step 1: Deploy Static Files to GitHub Pages**

```bash
# In your repo, create a gh-pages branch with just static/
git checkout -b gh-pages
git rm -rf . (except static/)
git mv static/* .
git commit -m "Deploy to GitHub Pages"
git push origin gh-pages

# Enable GitHub Pages in repo settings → Source: gh-pages branch
```

**Step 2: Update WebSocket URL in client.js**

```javascript
// In client.js, find the connect() function and update:
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.hostname === 'your-username.github.io'
    ? 'your-pi-ip:8080'  // Your Pi's IP or Tailscale address
    : window.location.host;
const wsUrl = `${protocol}//${host}/ws`;
```

**Step 3: Run Server on Raspberry Pi**

```bash
# SSH into Pi
ssh pi@your-pi-ip

# Clone repo
git clone https://github.com/your-username/mao-game.git
cd mao-game/mao_game

# Install
python3 -m venv venv
source venv/bin/activate
pip install aiohttp bcrypt

# Run (use screen or systemd for persistence)
make web
```

**Step 4: Access**
- GitHub Pages: `https://your-username.github.io/mao-game/`
- Connects to your Pi's WebSocket server

### Option 2: Self-Hosted (All-in-One)

Run everything on your Pi - simplest option.

```bash
# On Pi
make web PORT=80

# Access via http://your-pi-ip
```

### Option 3: Tailscale for Secure Access

Use Tailscale to access your Pi from anywhere without exposing ports.

```bash
# Install Tailscale on Pi
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# Get your Tailscale IP
tailscale ip
# → 100.x.y.z

# Access via http://100.x.y.z:8080
```

**Public Access with Tailscale Funnel:**
```bash
tailscale funnel 8080
# Gives public URL: https://your-name.ts.net
```

## Persistent Server (systemd)

Create `/etc/systemd/system/mao-game.service`:

```ini
[Unit]
Description=Mao Game Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mao-game/mao_game
Environment=PYTHONPATH=/home/pi/mao-game
ExecStart=/home/pi/mao-game/mao_game/venv/bin/python -m mao_game server --web --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mao-game
sudo systemctl start mao-game
```

## File Structure

```
mao_game/
├── config/
│   ├── mao_game.db    # SQLite database (auto-created)
│   ├── lobbies.json   # Lobby metadata
│   └── rules.json     # Game rules
├── database/          # Auth module
├── network/           # WebSocket server
├── static/           # Frontend (index.html, client.js, style.css)
└── core/             # Game logic
```

## Security Notes

- **HTTPS**: GitHub Pages provides HTTPS automatically
- **WSS**: For secure WebSocket, run server behind nginx with SSL
- **Passwords**: User and lobby passwords hashed with bcrypt
- **No tokens**: Session tied to WebSocket connection