# Mao Game Testing Guide

## Quick Start

### Run All Tests
```bash
cd /Users/hathsin/Desktop/claude_test/mao_game
source venv/bin/activate
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/test_game.py -v
python -m pytest tests/test_websocket_server.py -v
```

### Run Single Test
```bash
python -m pytest tests/test_game.py::TestGame::test_start_game -v
```

---

## Manual Browser Testing

### 1. Start the Server
```bash
cd /Users/hathsin/Desktop/claude_test/mao_game
source venv/bin/activate
python -m mao_game --web
```

Server runs at: **http://localhost:8080**

### 2. Test Multiple Players
Open 2+ browser tabs/windows to `http://localhost:8080`

1. **Tab 1**: Enter name "Alice", click Join
2. **Tab 2**: Enter name "Bob", click Join
3. **Either tab**: Click "Start Game"

### 3. Test Key Features

| Feature | How to Test |
|---------|-------------|
| **Play Card** | Click a card in your hand, then click the discard pile |
| **Draw Card** | Click the draw pile |
| **Point of Order** | Type "point of order" in chat |
| **Give Penalty** | Click another player → "Give Penalty" |
| **Throw Card** | Click a card, then click "Throw at Player" |
| **Hit Player** | Click another player → "Hit" |
| **Declare Mao** | When you have 1 card left, "Declare Mao" appears |
| **View Hand (POO)** | During Point of Order, click eye icon |

---

## Test Coverage

| File | Tests |
|------|-------|
| `test_game.py` | Game logic, turns, penalties, voting |
| `test_card.py` | Card creation, serialization |
| `test_deck.py` | Deck operations, shuffling |
| `test_player.py` | Player hand management |
| `test_protocol.py` | Message encoding/decoding |
| `test_websocket_server.py` | WebSocket connections, game flow |

---

## Common Test Scenarios

### Two-Player Game
1. Two players join
2. Game starts
3. Players take turns drawing/playing
4. First to empty hand wins (or declares Mao)

### Penalty Test
1. Start game with 2+ players
2. Player 1 gives penalty to Player 2
3. Player 2 should receive cards

### Point of Order Flow
1. During game, type "point of order" in chat
2. Game pauses, players can discuss
3. Vote on penalties
4. Type "end point of order" to resume

---

## Troubleshooting

### "Address already in use"
Another server is running on port 8080:
```bash
lsof -i :8080
kill -9 <PID>
```

### "Module not found"
Activate virtual environment:
```bash
source venv/bin/activate
```

### Tests fail with import errors
Run from project root:
```bash
cd /Users/hathsin/Desktop/claude_test/mao_game
python -m pytest tests/ -v
```