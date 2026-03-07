# Mao Card Game Makefile

.PHONY: help server client test clean lint format install run-local

# Default target
help:
	@echo "Mao Card Game - Available Commands:"
	@echo ""
	@echo "  make server       Start the game server (port 5555)"
	@echo "  make client       Start a client connecting to localhost"
	@echo "  make run-local    Start both server and a client for local testing"
	@echo "  make test         Run all unit tests"
	@echo "  make clean        Remove compiled Python files"
	@echo "  make lint         Run code linting (requires flake8)"
	@echo "  make format       Format code (requires black)"
	@echo ""
	@echo "Server Options:"
	@echo "  PORT=7777         Use custom port"
	@echo "  DECKS=2           Use multiple decks"
	@echo "  PLAYERS=3         Set minimum players"
	@echo ""
	@echo "Client Options:"
	@echo "  HOST=192.168.1.5  Connect to specific host"
	@echo "  NAME=Alice        Set player name"
	@echo ""
	@echo "Examples:"
	@echo "  make server PORT=7777 DECKS=2"
	@echo "  make client HOST=192.168.1.10 NAME=Bob"

# Start the server
server:
	@echo "Starting Mao server on port $(or $(PORT), 5555)..."
	cd mao_game && python3 server_main.py --port $(or $(PORT), 5555) --decks $(or $(DECKS), 1) --players $(or $(PLAYERS), 2)

# Start a client
client:
	@echo "Connecting to $(or $(HOST), localhost):$(or $(PORT), 5555)..."
	cd mao_game && python3 client_main.py --host $(or $(HOST), localhost) --port $(or $(PORT), 5555) --name "$(or $(NAME), Player)"

# Run tests
test:
	@echo "Running tests..."
	python3 -m unittest discover -s mao_game/tests -v

# Clean up compiled files
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Done!"

# Run linting (requires flake8)
lint:
	@echo "Running flake8..."
	@which flake8 > /dev/null || (echo "flake8 not installed. Run: pip install flake8" && exit 1)
	flake8 mao_game/ --max-line-length=100 --exclude=tests/

# Format code (requires black)
format:
	@echo "Formatting code with black..."
	@which black > /dev/null || (echo "black not installed. Run: pip install black" && exit 1)
	black mao_game/ --line-length=100

# Local testing - start server in background and connect client
run-local:
	@echo "Starting local game (server + client)..."
	@echo "Server starting in background..."
	@cd mao_game && python3 server_main.py &
	@sleep 1
	@echo "Starting client..."
	@cd mao_game && python3 client_main.py --host localhost --name "Player1"

# Check Python version
check-python:
	@python3 --version || (echo "Python 3 is required" && exit 1)

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install flake8 black pytest
	@echo "Done!"

# Quick syntax check
syntax:
	@echo "Checking Python syntax..."
	@python3 -m py_compile mao_game/core/*.py mao_game/network/*.py mao_game/ui/*.py
	@echo "Syntax OK!"