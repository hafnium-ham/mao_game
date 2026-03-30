.PHONY: help install server web client test clean

# Get the directory where this Makefile is located
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
VENV_PYTHON := $(MAKEFILE_DIR)venv/bin/python

# Use venv python if available, otherwise system python3
PYTHON := $(shell if [ -x "$(VENV_PYTHON)" ]; then echo "$(VENV_PYTHON)"; else echo python3; fi)

help:
	@echo "Mao Card Game"
	@echo ""
	@echo "  make install   Install dependencies"
	@echo "  make web       Start web server (default port 8080)"
	@echo "  make server    Start CLI server"
	@echo "  make client    Start CLI client"
	@echo "  make test      Run tests"
	@echo "  make clean     Clean build artifacts"
	@echo ""
	@echo "Options:"
	@echo "  PORT=8080      Set port"
	@echo "  HOST=localhost Set host for client"
	@echo "  NAME=Player    Set player name"

install:
	$(PYTHON) -m pip install -r requirements.txt

web:
	cd .. && $(PYTHON) -m mao_game server --web --port $(or $(PORT), 8080)

server:
	cd .. && $(PYTHON) -m mao_game server --port $(or $(PORT), 5555)

client:
	cd .. && $(PYTHON) -m mao_game client --host $(or $(HOST), localhost) --port $(or $(PORT), 5555) --name "$(or $(NAME), Player)"

test:
	cd .. && $(PYTHON) -m pytest mao_game/tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".DS_Store" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "Cleaned!"