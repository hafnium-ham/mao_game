# Mao Card Game Makefile - Fixed for local directory execution

.PHONY: help server client web test clean

# Default target
help:
	@echo "Mao Card Game - Available Commands:"
	@echo ""
	@echo "  make server       Start the CLI game server"
	@echo "  make web          Start the web server (browser clients)"
	@echo "  make client       Start a CLI client"
	@echo "  make test         Run all unit tests"
	@echo ""
	@echo "Web Server Options:"
	@echo "  PORT=8080         Set the port (default 8080)"
	@echo ""
	@echo "CLI Connection Options:"
	@echo "  HOST=172.24.33.100  Set the IP of the server"
	@echo "  NAME=YourName       Set your player name"
	@echo "  PORT=5555           Set the port (default 5555)"
	@echo ""
	@echo "Example:"
	@echo "  make web PORT=8080"

# Start the CLI server
server:
	@echo "Starting Mao CLI server..."
	@echo "----------------------------------------------------------------"
	@echo "YOUR IP ADDRESS: $$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $$2}' | head -n 1)"
	@echo "Give the IP above to your friends so they can join!"
	@echo "----------------------------------------------------------------"
	PYTHONPATH=.. python3 main.py server --port $(or $(PORT), 5555) --decks $(or $(DECKS), 1) --max-players $(or $(PLAYERS), 10)

# Start the web server for browser clients
web:
	@echo "Starting Mao web server..."
	@echo "----------------------------------------------------------------"
	@echo "Open http://localhost:$(or $(PORT), 8080) in your browser"
	@echo "----------------------------------------------------------------"
	PYTHONPATH=.. python3 main.py server --web --port $(or $(PORT), 8080)

# Start a CLI client
client:
	@echo "Connecting to $(or $(HOST), localhost):$(or $(PORT), 5555)..."
	PYTHONPATH=.. python3 main.py client --host $(or $(HOST), localhost) --port $(or $(PORT), 5555) --name "$(or $(NAME), Player)"

# Run tests
test:
	@echo "Running tests..."
	PYTHONPATH=.. python3 -m unittest discover -s tests -v

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Done!"