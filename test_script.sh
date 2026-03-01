#!/bin/bash

# Test script for Mao Game - Opens multiple terminal windows to test the game

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           MAO GAME TEST SCRIPT                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: main.py not found. Please run this script from the mao_game directory.${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 is required but not installed.${NC}"
    exit 1
fi

# Check if we're in a virtual environment (optional check)
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Not running in a virtual environment. Consider using one for dependencies.${NC}"
    echo ""
fi

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

# Find an available port
find_available_port() {
    local start_port=$1
    local port=$start_port
    
    while ! check_port $port; do
        port=$((port + 1))
    done
    
    echo $port
}

# Default port
DEFAULT_PORT=5555

# Check if default port is available
if check_port $DEFAULT_PORT; then
    PORT=$DEFAULT_PORT
    echo -e "${GREEN}✓ Port $DEFAULT_PORT is available${NC}"
else
    echo -e "${YELLOW}Port $DEFAULT_PORT is in use, finding alternative...${NC}"
    PORT=$(find_available_port 5556)
    echo -e "${GREEN}✓ Using port $PORT${NC}"
fi

echo ""
echo -e "${BLUE}Starting Mao Game test with $PORT...${NC}"
echo ""

# Function to open terminal and run command
open_terminal() {
    local title="$1"
    local command="$2"
    
    # Try different terminal emulators based on the system
    if command -v osascript &> /dev/null; then
        # macOS
        osascript -e "tell application \"Terminal\" to do script \"$command\""
        osascript -e "tell application \"Terminal\" to set custom title of front window to \"$title\""
    elif command -v gnome-terminal &> /dev/null; then
        # GNOME Terminal (Linux)
        gnome-terminal --title="$title" -- bash -c "$command; read -p 'Press Enter to close...'"
    elif command -v konsole &> /dev/null; then
        # Konsole (Linux)
        konsole --title "$title" -e bash -c "$command; read -p 'Press Enter to close...'"
    elif command -v xterm &> /dev/null; then
        # xterm (Linux)
        xterm -T "$title" -e bash -c "$command; read -p 'Press Enter to close...'"
    elif command -v powershell &> /dev/null; then
        # Windows PowerShell
        powershell.exe -Command "Start-Process powershell -ArgumentList '-NoExit', '-Command', 'Write-Host \"$title\"; $command'"
    else
        echo -e "${RED}Error: No supported terminal emulator found.${NC}"
        echo "Please manually open terminals and run:"
        echo "1. python3 main.py server --port $PORT"
        echo "2. python3 main.py client --port $PORT --name Player1"
        echo "3. python3 main.py client --port $PORT --name Player2"
        return 1
    fi
}

# Start the server
echo -e "${GREEN}Starting server...${NC}"
SERVER_COMMAND="cd $(pwd) && python3 main.py server --port $PORT"
open_terminal "Mao Server" "$SERVER_COMMAND"

# Wait a moment for server to start
sleep 2

# Start first client
echo -e "${GREEN}Starting Player 1...${NC}"
CLIENT1_COMMAND="cd $(pwd) && python3 main.py client --port $PORT --name Player1"
open_terminal "Mao Player 1" "$CLIENT1_COMMAND"

# Wait a moment
sleep 1

# Start second client
echo -e "${GREEN}Starting Player 2...${NC}"
CLIENT2_COMMAND="cd $(pwd) && python3 main.py client --port $PORT --name Player2"
open_terminal "Mao Player 2" "$CLIENT2_COMMAND"

# Wait a moment
sleep 1

# Start third client (optional)
echo -e "${GREEN}Starting Player 3...${NC}"
CLIENT3_COMMAND="cd $(pwd) && python3 main.py client --port $PORT --name Player3"
open_terminal "Mao Player 3" "$CLIENT3_COMMAND"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           TEST SETUP COMPLETE                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Instructions:${NC}"
echo "1. The server window will show game status and logs"
echo "2. Each player window allows individual gameplay"
echo "3. Try playing cards, using commands, and discovering rules"
echo "4. Test different scenarios with multiple players"
echo ""
echo -e "${YELLOW}Common test scenarios:${NC}"
echo "- Test card playing rules"
echo "- Test penalty system"
echo "- Test special cards (Ace, 7, 8, etc.)"
echo "- Test player joining/leaving"
echo "- Test rule enforcement"
echo ""
echo -e "${YELLOW}To stop all terminals:${NC}"
echo "- Close each terminal window manually"
echo "- Or use Ctrl+C in each window"
echo ""
echo -e "${GREEN}Happy testing! 🃏${NC}"