# Mao Card Game Makefile - Fixed for local directory execution

.PHONY: help server client test clean lint format install run-local

# Default target
help:
	@echo "Mao Card Game - Available Commands:"
	@echo ""
	@echo "  make server       Start the game server"
	@echo "  make client       Start a client (connects to localhost by default)"
	@echo "  make run-local    Start server and one client automatically"
	@echo "  make test         Run all unit tests"
	@echo ""
	@echo "Connection Options (How to play with friends):"
	@echo "  HOST=172.24.33.100  Set the IP of the server computer"
	@echo "  NAME=YourName       Set your player name"
	@echo "  PORT=5555           Set the port (default 5555)"
	@echo ""
	@echo "Example for Friends:"
	@echo "  make client HOST=172.24.33.100 NAME=Alice"

# Start the server
# Fixed the --players to --max-players typo
server:
	@echo "Starting Mao server..."
	@echo "----------------------------------------------------------------"
	@echo "YOUR IP ADDRESS: $$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $$2}' | head -n 1)"
	@echo "Give the IP above to your friends so they can join!"
	@echo "----------------------------------------------------------------"
	PYTHONPATH=.. python3 main.py server --port $(or $(PORT), 5555) --decks $(or $(DECKS), 1) --max-players $(or $(PLAYERS), 2)

# Start a client
# Uses main.py to avoid the ModuleNotFoundError
client:
	@echo "Connecting to $(or $(HOST), localhost):$(or $(PORT), 5555)..."
	PYTHONPATH=.. python3 main.py client --host $(or $(HOST), localhost) --port $(or $(PORT), 5555) --name "$(or $(NAME), Player)"

# Run tests
test:
	@echo "Running tests..."
	PYTHONPATH=.. python3 -m unittest discover -s tests -v

# Local testing
run-local:
	@echo "Starting local game..."
	PYTHONPATH=.. python3 main.py server &
	@sleep 1
	PYTHONPATH=.. python3 main.py client --host localhost --name "Player1"

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Done!"