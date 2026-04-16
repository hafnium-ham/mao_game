/**
 * Mao Card Game - WebSocket Client
 *
 * This client handles real-time communication with the game server via WebSocket.
 * It manages:
 * - Player authentication and session management
 * - Lobby creation and joining
 * - Game state synchronization
 * - UI rendering for cards, players, and game phases
 * - Point of Order (POO) voting and penalty system
 * - Avatar upload with drag/zoom cropping
 *
 * Architecture:
 * - Connection is established on intro screen, maintained throughout session
 * - Server broadcasts game state changes to all clients
 * - Client actions send messages, server validates and broadcasts updates
 * - localStorage is used for preferences (theme, keybinds, avatar) with fallback
 *
 * Key Message Types:
 * - connect: Initial connection and name registration
 * - game_state: Full game state sync
 * - hand_update: Player's card hand
 * - notification: Game events (plays, penalties, etc.)
 * - point_of_order: POO state management
 * - vote: Penalty voting during POO
 */

// Card suit symbols for display
const SUIT_SYMBOLS = {
    'hearts': '♥',
    'diamonds': '♦',
    'clubs': '♣',
    'spades': '♠',
    'h': '♥',
    'd': '♦',
    'c': '♣',
    's': '♠'
};

// Rank name mapping for card image filenames
const RANK_NAMES = {
    'j': 'jack',
    'q': 'queen',
    'k': 'king',
    'a': 'ace'
};

/**
 * Convert rank to image filename format.
 * @param {string} rank - Card rank (A, K, Q, J, 10, etc.)
 * @returns {string} Rank name for filename
 */
function getRankName(rank) {
    const lower = (rank || '').toString().toLowerCase();
    return RANK_NAMES[lower] || lower;
}

// CSS class constants
const HIDDEN_CLASS = 'hidden';

/**
 * Extract field from message data, handling both direct and nested formats.
 * Server messages may have {field: value} or {data: {field: value}}.
 */
function extractField(data, field, defaultValue = null) {
    return data[field] ?? data.data?.[field] ?? defaultValue;
}

// Modal visibility helpers
function showModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove(HIDDEN_CLASS);
}

function hideModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add(HIDDEN_CLASS);
}

// Cached DOM elements for performance
const DOM = {};
function cacheDom() {
    DOM.chatMessages = document.getElementById('chat-messages');
    DOM.stackCards = document.getElementById('stack-cards');
    DOM.recentCards = document.getElementById('recent-cards');
    DOM.notifications = document.getElementById('notifications');
    DOM.myHand = document.getElementById('my-hand');
}

// Game state variables
let playerId = null;          // Current player's unique ID
let playerName = null;         // Current player's display name
let gameState = null;          // Current game state from server
let myHand = [];              // Player's current hand
let selectedPlayerId = null;   // Target for player actions
let viewingHand = false;       // POO hand visibility state
let pooActive = false;         // Point of Order active flag
let currentLobbyCode = null;   // Current lobby code
let currentTheme = 'dark';     // UI theme preference

/**
 * Safe localStorage wrapper - handles blocked storage in non-private browsing.
 * Some browsers block localStorage in certain contexts (e.g., third-party iframes).
 * These helpers provide fallback behavior when storage is unavailable.
 */
function safeGetItem(key, defaultValue = null) {
    try {
        const value = localStorage.getItem(key);
        return value !== null ? JSON.parse(value) : defaultValue;
    } catch (e) {
        console.warn('localStorage not available:', e);
        return defaultValue;
    }
}

function safeSetItem(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (e) {
        console.warn('localStorage not available:', e);
        return false;
    }
}

function safeGetRawItem(key, defaultValue = null) {
    try {
        const value = localStorage.getItem(key);
        return value !== null ? value : defaultValue;
    } catch (e) {
        console.warn('localStorage not available:', e);
        return defaultValue;
    }
}

function safeSetRawItem(key, value) {
    try {
        localStorage.setItem(key, value);
        return true;
    } catch (e) {
        console.warn('localStorage not available:', e);
        return false;
    }
}

// Penalty reasons (stored in localStorage)
let penaltyReasons = safeGetItem('mao_penaltyReasons', []);

// Default penalty cards
let defaultPenaltyCards = parseInt(safeGetRawItem('mao_penaltyCards', '1')) || 1;

// Default keybinds
const DEFAULT_KEYBINDS = {
    draw: 'd',
    knock: 'k',
    mao: 'm',
    chat: 's'
};
let keybinds = safeGetItem('mao_keybinds', { ...DEFAULT_KEYBINDS });

// Theme management
function setTheme(theme) {
    currentTheme = theme;
    // Remove all theme classes and add the new one
    document.body.className = theme === 'dark' ? '' : `theme-${theme}`;
    safeSetRawItem('mao_theme', theme);

    // Update active button
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === theme);
    });
}

// Initialize theme from localStorage
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = safeGetRawItem('mao_theme', 'dark');
    setTheme(savedTheme);

    // Restore user session
    restoreSession();

    // Theme buttons
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', () => setTheme(btn.dataset.theme));
    });

    // Name input enable continue button
    const nameInput = document.getElementById('player-name');
    const continueBtn = document.getElementById('continue-btn');

    nameInput.addEventListener('input', () => {
        continueBtn.disabled = nameInput.value.trim().length < 1;
    });

    continueBtn.addEventListener('click', handleIntroContinue);
    nameInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && nameInput.value.trim()) {
            handleIntroContinue();
        }
    });

    // Auth buttons
    document.getElementById('login-toggle-link').addEventListener('click', (e) => {
        e.preventDefault();
        toggleAuthForm();
    });
    document.getElementById('auth-submit-btn').addEventListener('click', submitAuth);
    document.getElementById('auth-toggle-btn').addEventListener('click', () => {
        if (isRegisterMode) {
            showLoginForm();
        } else {
            showRegisterForm();
        }
    });
    document.getElementById('auth-cancel-btn').addEventListener('click', () => {
        document.getElementById('login-form').classList.add('hidden');
    });
    document.getElementById('auth-password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitAuth();
    });

    // Lobby buttons
    document.getElementById('create-lobby-btn').addEventListener('click', createLobby);
    document.getElementById('refresh-lobbies-btn').addEventListener('click', requestLobbyList);
    document.getElementById('confirm-join-btn').addEventListener('click', confirmJoinLobby);

    // Legacy lobby buttons
    document.getElementById('start-btn').addEventListener('click', startGame);
    document.getElementById('leave-btn').addEventListener('click', leaveLobby);
    document.getElementById('settings-btn').addEventListener('click', showSettingsModal);

    // Populate penalty reasons
    updatePenaltyReasonsSelect();

    // Initialize draggable chat
    initDraggableChat();
});

// Draggable chat panel with edge snapping
function initDraggableChat() {
    const panel = document.getElementById('chat-panel');
    const header = document.getElementById('chat-drag-handle');
    if (!panel || !header) return;

    let dragging = false;
    let offset = { x: 0, y: 0 };

    // Load saved position
    const savedPos = safeGetItem('mao_chatPos', {});
    if (savedPos.left !== undefined) {
        panel.style.left = savedPos.left + 'px';
        panel.style.top = savedPos.top + 'px';
        panel.style.right = 'auto';
        panel.style.bottom = 'auto';
    }

    header.addEventListener('mousedown', (e) => {
        // Only start drag on left click, not on toggle click
        if (e.button !== 0) return;
        dragging = true;
        const rect = panel.getBoundingClientRect();
        offset.x = e.clientX - rect.left;
        offset.y = e.clientY - rect.top;
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;

        let x = e.clientX - offset.x;
        let y = e.clientY - offset.y;

        // Edge snapping threshold
        const snapThreshold = 20;

        // Snap to left edge
        if (x < snapThreshold) x = 10;
        // Snap to top edge
        if (y < snapThreshold) y = 10;
        // Snap to right edge
        if (x + panel.offsetWidth > window.innerWidth - snapThreshold) {
            x = window.innerWidth - panel.offsetWidth - 10;
        }
        // Snap to bottom edge
        if (y + panel.offsetHeight > window.innerHeight - snapThreshold) {
            y = window.innerHeight - panel.offsetHeight - 10;
        }

        panel.style.left = x + 'px';
        panel.style.top = y + 'px';
        panel.style.right = 'auto';
        panel.style.bottom = 'auto';
    });

    document.addEventListener('mouseup', (e) => {
        if (dragging) {
            dragging = false;
            // Save position
            safeSetItem('mao_chatPos', {
                left: parseInt(panel.style.left) || 10,
                top: parseInt(panel.style.top) || 140
            });
        }
    });

    // Toggle chat on header click (but not during drag)
    let clickStart = 0;
    header.addEventListener('click', (e) => {
        if (Date.now() - clickStart < 200) {
            toggleChat();
        }
    });
    header.addEventListener('mousedown', () => clickStart = Date.now());
}

// Intro screen flow
function handleIntroContinue() {
    playerName = document.getElementById('player-name').value.trim();
    if (!playerName) return;

    // Connect to server
    connect(() => {
        // After connection, request lobby list and show lobby browser
        showScreen('lobby-browser');
        requestLobbyList();
    });
}

// Connection
function connect(callback) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        const savedAvatar = safeGetRawItem('mao_avatar');
        sendMessage({
            type: 'connect',
            data: { name: playerName, avatar: savedAvatar || null }
        });
        if (callback) callback();
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Received:', data.type, data);
            handleMessage(data);
        } catch (e) {
            console.error('Failed to parse message:', event.data, e);
        }
    };

    ws.onclose = () => {
        showStatus('Disconnected from server', 'error');
        playerId = null;
        gameState = null;
        currentLobbyCode = null;
    };

    ws.onerror = (error) => {
        showStatus('Connection error', 'error');
        console.error('WebSocket error:', error);
    };
}

function sendMessage(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('Sending:', msg.type, msg);
        ws.send(JSON.stringify(msg));
    }
}

function handleMessage(data) {
    const handler = messageHandlers[data.type];
    if (handler) {
        handler(data);
    } else {
        console.log('Unknown message type:', data.type, data);
    }
}

// Message type handlers
const messageHandlers = {
    'connect': handleConnect,
    'login_success': handleLoginSuccess,
    'lobby_list': handleLobbyList,
    'lobby_created': handleLobbyCreated,
    'lobby_joined': handleLobbyJoined,
    'lobby_error': handleLobbyError,
    'player_list': handlePlayerList,
    'game_state': handleGameState,
    'hand_update': handleHandUpdate,
    'card_drawn': handleCardDrawn,
    'penalty': handlePenalty,
    'notification': handleNotification,
    'point_of_order': handlePointOfOrder,
    'game_over': handleGameOver,
    'error': handleError,
    'success': handleSuccess,
    'mao_declared': handleMaoDeclared,
    'game_log': handleGameLog,
    'avatar_update': handleAvatarUpdate
};

// Auth state
let currentUser = null;  // { id, username, display_name, avatar }
let isRegisterMode = false;

// Message Handlers
function handleConnect(data) {
    playerId = data.player_id || data.data?.player_id;
    const name = data.name || data.data?.name || playerName;
    showStatus(`Connected as ${name}`, 'success');
}

function handleLoginSuccess(data) {
    const user = data.data || data;
    currentUser = {
        id: user.user_id,
        username: user.username,
        display_name: user.display_name || user.username,
        avatar: user.avatar
    };

    // Update UI
    const nameInput = document.getElementById('player-name');
    nameInput.value = currentUser.display_name;

    const loginStatus = document.getElementById('login-status');
    loginStatus.textContent = `Logged in as ${currentUser.display_name}`;

    const loginForm = document.getElementById('login-form');
    loginForm.classList.add('hidden');

    // Save session
    safeSetItem('mao_user', currentUser);

    showStatus(`Logged in as ${currentUser.display_name}`, 'success');

    // If connected, update name
    if (ws && ws.readyState === WebSocket.OPEN) {
        sendMessage({
            type: 'connect',
            data: { name: currentUser.display_name, avatar: currentUser.avatar }
        });
    }
}

// Auth UI functions
function toggleAuthForm() {
    const loginForm = document.getElementById('login-form');
    loginForm.classList.toggle('hidden');
}

function showRegisterForm() {
    isRegisterMode = true;
    document.getElementById('auth-title').textContent = 'Register';
    document.getElementById('auth-submit-btn').textContent = 'Register';
    document.getElementById('auth-display-name').classList.remove('hidden');
    document.getElementById('auth-toggle-btn').textContent = 'Back to Login';
}

function showLoginForm() {
    isRegisterMode = false;
    document.getElementById('auth-title').textContent = 'Login';
    document.getElementById('auth-submit-btn').textContent = 'Login';
    document.getElementById('auth-display-name').classList.add('hidden');
    document.getElementById('auth-toggle-btn').textContent = 'Register';
}

function submitAuth() {
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;
    const displayName = document.getElementById('auth-display-name').value.trim();

    if (!username || !password) {
        showStatus('Username and password required', 'error');
        return;
    }

    if (isRegisterMode) {
        sendMessage({
            type: 'register',
            data: { username, password, display_name: displayName || username }
        });
    } else {
        sendMessage({
            type: 'login',
            data: { username, password }
        });
    }
}

function logout() {
    sendMessage({ type: 'logout' });
    currentUser = null;
    safeSetItem('mao_user', null);
    document.getElementById('login-status').textContent = '';
    showStatus('Logged out', 'success');
}

// Restore session from localStorage
function restoreSession() {
    const saved = safeGetItem('mao_user');
    if (saved) {
        try {
            currentUser = saved;
            document.getElementById('player-name').value = currentUser.display_name;
            document.getElementById('login-status').textContent = `Logged in as ${currentUser.display_name}`;
        } catch (e) {
            safeSetItem('mao_user', null);
        }
    }
}

// Lobby Handlers
function handleLobbyList(data) {
    const lobbies = data.lobbies || data.data?.lobbies || [];
    renderLobbyList(lobbies);
}

function handleLobbyCreated(data) {
    const code = data.code || data.data?.code;
    const name = data.name || data.data?.name;
    const maxPlayers = data.max_players || data.data?.max_players || 10;
    const numDecks = data.num_decks || data.data?.num_decks || 1;
    currentLobbyCode = code;

    // Update lobby display
    const maxPlayersEl = document.getElementById('max-players');
    const deckCountEl = document.getElementById('deck-count');
    if (maxPlayersEl) maxPlayersEl.textContent = maxPlayers;
    if (deckCountEl) deckCountEl.textContent = numDecks;

    showStatus(`Lobby "${name}" created! Code: ${code}`, 'success');
    // Auto-join the lobby (already done on server side)
    showScreen('lobby');
}

function handleLobbyJoined(data) {
    const code = data.code || data.data?.code;
    const name = data.name || data.data?.name;
    const maxPlayers = data.max_players || data.data?.max_players || 10;
    const numDecks = data.num_decks || data.data?.num_decks || 1;
    const hostId = data.host_id || data.data?.host_id;
    currentLobbyCode = code;
    lobbyHostId = hostId;

    // Update lobby display
    const maxPlayersEl = document.getElementById('max-players');
    const deckCountEl = document.getElementById('deck-count');
    if (maxPlayersEl) maxPlayersEl.textContent = maxPlayers;
    if (deckCountEl) deckCountEl.textContent = numDecks;

    showStatus(`Joined lobby "${name}"`, 'success');
    showScreen('lobby');
}

function handleLobbyError(data) {
    const message = data.message || data.data?.message || 'Lobby error';
    showStatus(message, 'error');
}

// Lobby Functions
function requestLobbyList() {
    sendMessage({ type: 'list_lobbies' });
}

function createLobby() {
    const nameInput = document.getElementById('lobby-name-input');
    const passwordInput = document.getElementById('lobby-password-input');
    const decksSelect = document.getElementById('lobby-decks-select');
    const maxPlayersSelect = document.getElementById('lobby-max-players-select');

    const name = nameInput.value.trim() || 'Game';
    const password = passwordInput.value.trim(); // Optional - empty string means no password
    const numDecks = parseInt(decksSelect?.value) || 1;
    const maxPlayers = parseInt(maxPlayersSelect?.value) || 10;

    sendMessage({
        type: 'create_lobby',
        data: {
            name,
            password,  // Can be empty string for no password
            num_decks: numDecks,
            max_players: maxPlayers
        }
    });
}

let selectedLobbyCode = null;

function confirmJoinLobby() {
    const passwordInput = document.getElementById('join-password-input');
    const password = passwordInput.value.trim();

    // Password only required for password-protected lobbies
    sendMessage({
        type: 'join_lobby',
        data: { code: selectedLobbyCode, password }
    });

    closeJoinModal();
}

function showJoinModal(lobbyCode, lobbyName) {
    selectedLobbyCode = lobbyCode;
    const hasPassword = lobbyPasswordMap[lobbyCode];

    document.getElementById('join-lobby-name').textContent = lobbyName;
    document.getElementById('join-password-input').value = '';

    // Show/hide password prompt based on whether lobby has password
    const passwordPrompt = document.getElementById('join-password-prompt');
    const passwordInput = document.getElementById('join-password-input');

    if (hasPassword) {
        passwordPrompt.textContent = 'Enter password';
        passwordInput.placeholder = 'Password required';
        passwordInput.required = true;
    } else {
        passwordPrompt.textContent = 'No password required';
        passwordInput.placeholder = 'Password (optional)';
        passwordInput.required = false;
    }

    document.getElementById('join-lobby-modal').classList.remove('hidden');
}

function closeJoinModal() {
    document.getElementById('join-lobby-modal').classList.add('hidden');
    selectedLobbyCode = null;
}

// Track which lobbies have passwords
let lobbyPasswordMap = {};

function renderLobbyList(lobbies) {
    const container = document.getElementById('lobby-list');

    if (lobbies.length === 0) {
        container.innerHTML = '<div class="no-lobbies">No lobbies available. Create one!</div>';
        return;
    }

    // Store password info for each lobby
    lobbyPasswordMap = {};
    lobbies.forEach(lobby => {
        lobbyPasswordMap[lobby.code] = lobby.has_password;
    });

    container.innerHTML = lobbies.map(lobby => `
        <div class="lobby-card" onclick="showJoinModal('${lobby.code}', '${lobby.name}')">
            <h3>${lobby.name} ${lobby.has_password ? '[locked]' : ''}</h3>
            <div class="lobby-info">
                <span>Players: ${lobby.player_count}/${lobby.max_players || 10}</span>
                <span>Code: ${lobby.code}</span>
            </div>
            <span class="lobby-status ${lobby.phase}">${lobby.phase === 'waiting' ? 'Waiting' : 'In Progress'}</span>
        </div>
    `).join('');
}

function leaveLobby() {
    if (currentLobbyCode) {
        sendMessage({ type: 'leave_lobby' });
        currentLobbyCode = null;
        showScreen('lobby-browser');
        requestLobbyList();
    }
}

function handlePlayerList(data) {
    const players = data.players || data.data?.players || [];
    const hostId = data.host_id || data.data?.host_id;
    lobbyHostId = hostId;

    // Store avatars from player list
    players.forEach(player => {
        if (player.avatar) {
            playerAvatars[player.id] = player.avatar;
        }
    });

    updatePlayerListDisplay(players, 'lobby');
}

function handleGameState(data) {
    gameState = data.data || data;
    console.log('Game state:', gameState);

    // Extract avatars from players list
    if (gameState.players) {
        gameState.players.forEach(player => {
            if (player.avatar) {
                playerAvatars[player.id] = player.avatar;
            }
        });
    }

    // Extract my hand from players list if present
    if (gameState.players && playerId) {
        const myPlayer = gameState.players.find(p => p.id === playerId);
        if (myPlayer && myPlayer.hand) {
            myHand = myPlayer.hand;
            renderHand();
        }
    }

    // Update UI based on game phase
    if (gameState.phase === 'waiting') {
        showScreen('lobby');
        updateLobby();
    } else if (gameState.phase === 'in_progress' || gameState.phase === 'point_of_order') {
        showScreen('game');
        updateGameDisplay();

        // Handle POO state
        if (gameState.phase === 'point_of_order') {
            activatePooMode();
        } else {
            deactivatePooMode();
        }
    } else if (gameState.phase === 'finished') {
        // Handled by game_over message
    }

    // Update keyboard shortcut availability
    updateKeyboardShortcuts();
}

function updateLobby() {
    const players = gameState.players || [];
    updatePlayerListDisplay(players, 'lobby');
    document.getElementById('start-btn').disabled = players.length < 2;
}

function updatePlayerListDisplay(players, mode) {
    const containerId = mode === 'lobby' ? 'players-list' : 'other-players';
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = '';

    players.forEach(player => {
        const div = document.createElement('div');
        const isYou = player.id === playerId;

        if (mode === 'lobby') {
            div.className = 'player-card' + (isYou ? ' is-you' : '');
            div.innerHTML = `
                <span class="name">${player.name}${isYou ? ' (You)' : ''}</span>
                <span class="count">${player.card_count || 0} cards</span>
            `;
        } else {
            div.className = 'player-slot' + (gameState.current_player_id === player.id ? ' current-turn' : '');
            div.innerHTML = `
                <div class="player-avatar">${player.name.charAt(0).toUpperCase()}</div>
                <div class="player-name">${player.name}</div>
                <div class="player-card-count">${player.card_count || 0} cards</div>
            `;
            div.addEventListener('click', () => showPlayerActions(player));
        }
        container.appendChild(div);
    });

    // Update player count in lobby
    if (mode === 'lobby') {
        document.getElementById('player-count').textContent = players.length;
    }
}

function updateGameDisplay() {
    if (!gameState) return;

    // Update players
    updatePlayerPositions();

    // Update my player info
    const myPlayer = gameState.players?.find(p => p.id === playerId);
    if (myPlayer) {
        document.getElementById('current-player-name').textContent = myPlayer.name;
        document.getElementById('my-card-count').textContent = myPlayer.card_count || 0;
    }

    // Update discard pile
    updateDiscardPile();

    // Update draw pile count and card back
    document.getElementById('draw-count').textContent = gameState.draw_pile_count || 0;
    renderCardBack(document.getElementById('draw-card'));

    // Update recent cards
    updateRecentCards();

    // Update hand
    renderHand();
}

function updatePlayerPositions() {
    const container = document.getElementById('game-container');
    // Clear only player slots, keep other elements
    container.querySelectorAll('.player-slot').forEach(el => el.remove());

    if (!gameState || !gameState.players) return;

    // Get other players (not me)
    const otherPlayers = gameState.players.filter(p => p.id !== playerId);

    // Position other players at the top of the screen
    otherPlayers.forEach((player, index) => {
        const div = document.createElement('div');
        div.className = 'player-slot';
        div.dataset.playerId = player.id;

        if (gameState.current_player_id === player.id) {
            div.classList.add('current-turn');
        }

        const total = otherPlayers.length;
        const pos = getPlayerPositions(total)[index];

        div.style.left = pos.left;
        div.style.top = pos.top;

        // Render avatar - use image if available, otherwise initial letter
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'player-avatar';

        if (playerAvatars[player.id]) {
            const img = document.createElement('img');
            img.className = 'player-avatar-img';
            img.src = playerAvatars[player.id];
            img.alt = player.name;
            avatarDiv.appendChild(img);
        } else {
            avatarDiv.textContent = player.name.charAt(0).toUpperCase();
        }

        const nameDiv = document.createElement('div');
        nameDiv.className = 'player-name';
        nameDiv.textContent = player.name;

        const countDiv = document.createElement('div');
        countDiv.className = 'player-card-count';
        countDiv.textContent = `${player.card_count || 0}`;

        div.appendChild(avatarDiv);
        div.appendChild(nameDiv);
        div.appendChild(countDiv);

        div.addEventListener('click', () => showPlayerActions(player));

        container.appendChild(div);
    });
}

function getPlayerPositions(count) {
    // Simple horizontal layout at the top of the screen
    const positions = [];
    for (let i = 0; i < count; i++) {
        positions.push({
            left: `${(i + 1) * (100 / (count + 1))}%`,
            top: '60px'
        });
    }
    return positions;
}

function updateDiscardPile() {
    const topCardDiv = document.getElementById('top-card');

    // recent_cards format: [{player_name, card}, ...]
    let topCard = null;
    if (gameState.recent_cards && gameState.recent_cards.length > 0) {
        // Get the last card object
        const lastPlay = gameState.recent_cards[gameState.recent_cards.length - 1];
        topCard = lastPlay.card || lastPlay;  // Handle both formats
    } else if (gameState.top_card) {
        topCard = gameState.top_card;
    }

    if (!topCard) {
        topCardDiv.innerHTML = '<div class="card back">Empty</div>';
        return;
    }

    renderCard(topCardDiv, topCard);
}

function updateRecentCards() {
    const container = document.getElementById('recent-cards');
    const sidebarContainer = document.getElementById('stack-cards');
    container.innerHTML = '';
    if (sidebarContainer) sidebarContainer.innerHTML = '';

    if (!gameState.recent_cards || gameState.recent_cards.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';

    // Show last 6 plays INCLUDING current top card - newest first
    const recent = gameState.recent_cards.slice(-6).reverse();
    recent.forEach(play => {
        const card = play.card || play;
        const playerName = play.player_name || '';
        const suit = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';

        // Add to inline recent cards
        const div = document.createElement('div');
        div.className = 'recent-card';
        div.textContent = `${card.rank}${suit}`;
        div.title = playerName ? `${playerName} played` : '';
        container.appendChild(div);

        // Add to sidebar
        if (sidebarContainer) {
            const sidebarDiv = document.createElement('div');
            sidebarDiv.className = 'stack-card';
            sidebarDiv.innerHTML = `<span class="stack-rank">${card.rank}</span><span class="stack-suit">${suit}</span>`;
            sidebarContainer.appendChild(sidebarDiv);
        }
    });
}

function updateKeyboardShortcuts() {
    // Keyboard shortcuts only work when game is in progress
}

function renderCard(container, card) {
    container.innerHTML = '';

    const suitSymbol = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';

    // Try to use card image first
    const rank = (card.rank || card.Rank || '').toString();
    const suit = (card.suit || card.Suit || '').toLowerCase();
    const rankName = getRankName(rank);

    if (rankName && suit) {
        const cardName = `${rankName}_of_${suit}`;
        const imgPath = `/cards/${cardName}.png`;

        const img = new Image();
        img.src = imgPath;
        img.alt = `${rank} of ${suit}`;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'contain';

        img.onload = () => {
            container.innerHTML = '';
            container.appendChild(img);
        };

        img.onerror = () => {
            // Fallback to text representation
            container.innerHTML = `
                <span class="rank">${card.rank || card.Rank || '?'}</span>
                <span class="suit-symbol">${suitSymbol}</span>
            `;
        };
    } else {
        // Text fallback
        container.innerHTML = `
            <span class="rank">${card.rank || card.Rank || '?'}</span>
            <span class="suit-symbol">${suitSymbol}</span>
        `;
    }

    container.className = `card ${suit}`;
}

// Render a card back image
function renderCardBack(container) {
    container.innerHTML = '';
    container.className = 'card back';

    const img = new Image();
    img.src = '/cards/card_back.png';
    img.alt = 'Card back';
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'contain';

    img.onerror = () => {
        // Fallback to text
        container.innerHTML = '<span class="rank">?</span>';
    };

    container.appendChild(img);
}

function handleHandUpdate(data) {
    myHand = data.hand || data.data?.hand || [];
    renderHand();
}

function renderHand() {
    const handContainer = document.getElementById('my-hand');
    handContainer.innerHTML = '';

    myHand.forEach((card, index) => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${(card.suit || '').toLowerCase()}`;
        cardDiv.dataset.index = index;

        const suitSymbol = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';
        const rank = (card.rank || card.Rank || '').toString();
        const suit = (card.suit || card.Suit || '').toLowerCase();
        const rankName = getRankName(rank);

        if (rankName && suit) {
            const cardName = `${rankName}_of_${suit}`;
            const imgPath = `/cards/${cardName}.png`;

            const img = new Image();
            img.src = imgPath;
            img.alt = `${rank} of ${suit}`;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'contain';

            img.onload = () => {
                cardDiv.innerHTML = '';
                cardDiv.appendChild(img);
            };

            img.onerror = () => {
                cardDiv.innerHTML = `
                    <span class="rank">${card.rank || card.Rank || '?'}</span>
                    <span class="suit-symbol">${suitSymbol}</span>
                `;
            };
        } else {
            cardDiv.innerHTML = `
                <span class="rank">${card.rank || card.Rank || '?'}</span>
                <span class="suit-symbol">${suitSymbol}</span>
            `;
        }

        cardDiv.addEventListener('click', () => playCard(card));
        handContainer.appendChild(cardDiv);
    });

    document.getElementById('my-card-count').textContent = myHand.length;
}

function handleCardDrawn(data) {
    const cards = data.cards || data.data?.cards || [];
    showNotification(`You drew ${cards.length} card(s)`, 'draw');
}

function handlePenalty(data) {
    const reason = data.reason || data.data?.reason || 'No reason given';
    const cards = data.cards || data.data?.cards || 1;
    const caller = data.caller || data.data?.caller || 'Someone';
    showNotification(`Penalty: ${cards} card(s) - ${reason} (from ${caller})`, 'penalty');
}

function handleNotification(data) {
    // Handle various message formats
    let message = data.message || data.data?.message || '';
    const eventType = data.event_type || data.data?.event_type || 'default';

    // Handle nested data
    if (data.data && typeof data.data === 'object') {
        message = message || data.data.message || 'Event occurred';
    }

    showNotification(message, eventType);
    addChatMessage(message, eventType);  // Also add to chat history
}

// Chat history storage
let chatMessages = [];
const MAX_CHAT_MESSAGES = 100;

function toggleChat() {
    const messages = document.getElementById('chat-messages');
    const toggle = document.getElementById('chat-toggle');
    if (messages.style.display === 'none') {
        messages.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        messages.style.display = 'none';
        toggle.textContent = '▶';
    }
}

function addChatMessage(message, type = 'default') {
    // Store in history
    chatMessages.push({ message: message, type: type, time: new Date() });
    if (chatMessages.length > MAX_CHAT_MESSAGES) {
        chatMessages.shift();
    }

    // Add to chat panel
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `chat-message ${type}`;
    div.textContent = message;
    container.appendChild(div);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    // Check for POO commands
    const lowerMessage = message.toLowerCase();

    if (lowerMessage.includes('point of order')) {
        // Check if this is "end point of order" (end before "point of order")
        const pooIndex = lowerMessage.indexOf('point of order');
        const endIndex = lowerMessage.indexOf('end');

        // Only trigger END if "end" appears before "point of order"
        if (endIndex !== -1 && endIndex < pooIndex) {
            sendMessage({ type: 'end_point_of_order' });
        } else {
            sendMessage({
                type: 'point_of_order',
                data: { reason: message }
            });
        }
    } else {
        sendMessage({
            type: 'chat',
            data: { message: message }
        });
    }

    input.value = '';
}

function handlePointOfOrder(data) {
    pooActive = true;
    document.body.classList.add('poo-active');
    document.getElementById('poo-indicator').classList.remove('hidden');

    // Show POO action buttons
    document.getElementById('shuffle-btn').classList.remove('hidden');
    document.getElementById('end-poo-btn').classList.remove('hidden');

    // Collapse hand during POO
    const playerArea = document.querySelector('.player-area');
    const hand = document.getElementById('my-hand');
    if (playerArea && hand) {
        playerArea.classList.add('collapsed');
        hand.classList.add('collapsed');
        playerArea.onclick = togglePooHand;
    }

    const reason = data.reason || data.data?.reason || 'No reason given';
    const caller = data.caller_name || data.data?.caller_name || 'Someone';

    // Update the POO indicator banner text
    const reasonText = document.getElementById('poo-reason-text');
    if (reasonText) {
        reasonText.textContent = ` - ${caller}: ${reason}`;
    }

    // Update penalty history for voting (if penalty panel exists)
    const penaltyHistory = data.penalty_history || data.data?.penalty_history || [];
    updatePenaltyVoting(penaltyHistory);

    // Show vote panel if there's an active vote
    const activeVote = data.active_vote || data.data?.active_vote || null;
    showVotePanel(activeVote);
}

function updatePenaltyVoting(penaltyHistory) {
    const penaltyList = document.getElementById('penalty-list');
    if (!penaltyList) return;

    penaltyList.innerHTML = '';

    if (penaltyHistory.length === 0) {
        penaltyList.innerHTML = '<p>No penalties to vote on</p>';
    } else {
        penaltyHistory.forEach((penalty, index) => {
            const div = document.createElement('div');
            div.className = 'penalty-item' + (penalty.overturned ? ' overturned' : '');
            div.innerHTML = `${index + 1}. ${penalty.caller_name} → ${penalty.target_name}: ${penalty.reason} (${penalty.cards} cards)`;
            div.onclick = () => voteOnPenalty(index);
            penaltyList.appendChild(div);
        });
    }
}

function showVotePanel(activeVote) {
    const panel = document.getElementById('penalty-voting-panel');
    if (!activeVote || !panel) {
        if (panel) panel.classList.add('hidden');
        return;
    }

    const penalty = activeVote.penalty;
    document.getElementById('vote-penalty-desc').textContent =
        `${penalty.caller_name} → ${penalty.target_name}: ${penalty.reason} (${penalty.cards} cards)`;

    document.getElementById('vote-uphold-count').textContent = activeVote.uphold_count || 0;
    document.getElementById('vote-overturn-count').textContent = activeVote.overturn_count || 0;
    document.getElementById('vote-abstain-count').textContent = activeVote.abstain_count || 0;

    panel.classList.remove('hidden');
}

function castVote(vote) {
    sendMessage({
        type: 'vote',
        data: { vote: vote }
    });
}

function activatePooMode() {
    pooActive = true;
    document.body.classList.add('poo-active');
    document.getElementById('poo-indicator').classList.remove('hidden');
    // Show POO action buttons
    document.getElementById('shuffle-btn').classList.remove('hidden');
    document.getElementById('end-poo-btn').classList.remove('hidden');
    // Collapse hand during POO
    const playerArea = document.querySelector('.player-area');
    const hand = document.getElementById('my-hand');
    if (playerArea && hand) {
        playerArea.classList.add('collapsed');
        hand.classList.add('collapsed');
        playerArea.onclick = togglePooHand;
    }
}

let pooHandExpanded = false;

function togglePooHand() {
    const playerArea = document.querySelector('.player-area');
    const hand = document.getElementById('my-hand');

    if (!pooHandExpanded) {
        // Expand - view hand
        pooHandExpanded = true;
        hand.classList.remove('collapsed');
        playerArea.classList.remove('collapsed');
        playerArea.classList.add('expanded-announce');
        // Broadcast to all players that we're viewing hand
        sendMessage({ type: 'view_hand' });
        // Allow clicking again to collapse
        playerArea.onclick = collapsePooHand;
    }
}

function collapsePooHand() {
    const playerArea = document.querySelector('.player-area');
    const hand = document.getElementById('my-hand');

    pooHandExpanded = false;
    hand.classList.add('collapsed');
    playerArea.classList.remove('expanded-announce');
    playerArea.classList.add('collapsed');
    playerArea.onclick = togglePooHand;
}

function deactivatePooMode() {
    pooActive = false;
    pooHandExpanded = false;
    document.body.classList.remove('poo-active');
    document.getElementById('poo-indicator').classList.add('hidden');
    document.getElementById('poo-modal').classList.add('hidden');
    // Hide POO action buttons
    document.getElementById('shuffle-btn').classList.add('hidden');
    document.getElementById('end-poo-btn').classList.add('hidden');
    // Hide vote panel
    const votePanel = document.getElementById('penalty-voting-panel');
    if (votePanel) votePanel.classList.add('hidden');
    // Restore hand display
    const playerArea = document.querySelector('.player-area');
    const hand = document.getElementById('my-hand');
    if (playerArea && hand) {
        playerArea.classList.remove('collapsed', 'expanded-announce');
        hand.classList.remove('collapsed');
        playerArea.onclick = null;
    }
    viewingHand = false;
}

function showPooModal() {
    if (!pooActive) return;
    const modal = document.getElementById('poo-modal');
    modal.classList.remove('hidden');
}

function closePooModal() {
    document.getElementById('poo-modal').classList.add('hidden');
}

function handleGameOver(data) {
    const winnerName = data.winner_name || data.data?.winner_name || 'Unknown';
    const winnerId = data.winner_id || data.data?.winner_id;
    const cardCount = data.card_count || data.data?.card_count || 0;

    const modal = document.getElementById('game-over-modal');
    const winnerText = winnerId === playerId
        ? `You win with ${cardCount} cards remaining!`
        : `${winnerName} wins with ${cardCount} cards remaining!`;
    document.getElementById('winner-text').textContent = winnerText;
    modal.classList.remove('hidden');
}

function handleError(data) {
    const message = data.error || data.data?.message || data.message || 'An error occurred';
    showNotification(`Error: ${message}`, 'error');
    console.error('Server error:', data);
}

function handleSuccess(data) {
    const message = data.message || data.data?.message || 'Success';
    showNotification(message, 'success');
}

// Game Actions
function playCard(card) {
    if (!gameState) {
        showNotification('Game not started', 'error');
        return;
    }

    if (gameState.phase !== 'in_progress' && gameState.phase !== 'point_of_order') {
        showNotification('Cannot play right now', 'error');
        return;
    }

    sendMessage({
        type: 'play_card',
        data: { card: card, face_up: true }
    });
}

// Command menu toggle
function toggleCommandMenu() {
    const list = document.getElementById('command-list');
    const toggle = document.getElementById('command-toggle');
    if (list.classList.contains('show')) {
        list.classList.remove('show');
        toggle.textContent = '▼';
    } else {
        list.classList.add('show');
        toggle.textContent = '▲';
    }
}

function drawCard() {
    if (!gameState) {
        showNotification('Game not started', 'error');
        return;
    }

    sendMessage({ type: 'draw_card' });
}

function sendKnock() {
    sendMessage({ type: 'knock' });
}

function showSayDialog() {
    document.getElementById('say-modal').classList.remove('hidden');
    document.getElementById('say-input').focus();
}

function closeSayModal() {
    document.getElementById('say-modal').classList.add('hidden');
    document.getElementById('say-input').value = '';
}

function sendSay() {
    const message = document.getElementById('say-input').value.trim();
    if (message) {
        // Check for POO commands
        const lowerMessage = message.toLowerCase();

        if (lowerMessage.includes('point of order') && lowerMessage.includes('end')) {
            sendMessage({ type: 'end_point_of_order' });
        } else if (lowerMessage.includes('point of order')) {
            sendMessage({
                type: 'point_of_order',
                data: { reason: message }
            });
        } else {
            sendMessage({
                type: 'chat',
                data: { message: message }
            });
        }
        closeSayModal();
    }
}

function declareMao() {
    if (!gameState || gameState.phase !== 'in_progress') {
        showNotification('Can only declare Mao during game', 'error');
        return;
    }

    if (confirm('Declare Mao? This ends the game if unchallenged for 6 seconds.')) {
        sendMessage({ type: 'declare_mao' });
    }
}

function challengeMao() {
    if (!gameState || gameState.mao_declaring_player_id === playerId) {
        showNotification("You can't challenge your own Mao!", 'error');
        return;
    }
    sendMessage({ type: 'cancel_mao' });
    document.getElementById('mao-challenge').classList.add('hidden');
}

function handleMaoDeclared(data) {
    const declarerName = data.declarer_name || data.data?.declarer_name || 'Someone';
    const declarerId = data.declarer_id || data.data?.declarer_id;

    // Don't show challenge banner to the declarer
    if (declarerId === playerId) return;

    document.getElementById('mao-declarer').textContent = declarerName;
    const banner = document.getElementById('mao-challenge');
    banner.classList.remove('hidden');

    // Auto-hide after 6 seconds
    setTimeout(() => {
        banner.classList.add('hidden');
    }, 6000);
}

function startGame() {
    sendMessage({ type: 'start_game' });
}

function leaveGame() {
    sendMessage({ type: 'leave_game' });
    location.reload();
}

// Player Actions
function showPlayerActions(player) {
    if (player.id === playerId) return; // Can't interact with yourself

    selectedPlayerId = player.id;
    document.getElementById('player-action-name').textContent = player.name;
    document.getElementById('player-card-count').textContent = player.card_count || 0;
    document.getElementById('player-action-modal').classList.remove('hidden');
}

function closePlayerModal() {
    document.getElementById('player-action-modal').classList.add('hidden');
    selectedPlayerId = null;
}

function hitPlayer() {
    if (!selectedPlayerId) return;

    sendMessage({
        type: 'hit_player',
        data: { target_id: selectedPlayerId }
    });

    closePlayerModal();
}

// Throw card target (saved before closing player modal)
let throwTargetId = null;
let throwTargetName = null;

// Penalty target (saved before closing player modal)
let penaltyTargetId = null;
let penaltyTargetName = null;

function showThrowCardDialog() {
    if (!selectedPlayerId) return;

    // Save target before closing modal
    throwTargetId = selectedPlayerId;
    throwTargetName = document.getElementById('player-action-name').textContent;
    document.getElementById('throw-target-name').textContent = throwTargetName;
    document.getElementById('throw-card-modal').classList.remove('hidden');

    // Show cards from hand
    const throwHand = document.getElementById('throw-hand');
    throwHand.innerHTML = '';

    myHand.forEach((card, index) => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${(card.suit || '').toLowerCase()}`;
        const suitSymbol = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';
        const rank = (card.rank || '').toString();
        const suit = (card.suit || '').toLowerCase();
        const rankName = getRankName(rank);

        if (rankName && suit) {
            const cardName = `${rankName}_of_${suit}`;
            const imgPath = `/cards/${cardName}.png`;

            const img = new Image();
            img.src = imgPath;
            img.alt = `${rank} of ${suit}`;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'contain';

            img.onload = () => {
                cardDiv.innerHTML = '';
                cardDiv.appendChild(img);
            };

            img.onerror = () => {
                cardDiv.innerHTML = `
                    <span class="rank">${card.rank || '?'}</span>
                    <span class="suit-symbol">${suitSymbol}</span>
                `;
            };
        } else {
            cardDiv.innerHTML = `
                <span class="rank">${card.rank || '?'}</span>
                <span class="suit-symbol">${suitSymbol}</span>
            `;
        }
        cardDiv.onclick = () => throwCard(card);
        throwHand.appendChild(cardDiv);
    });

    closePlayerModal();
}

function closeThrowModal() {
    document.getElementById('throw-card-modal').classList.add('hidden');
}

function throwCard(card) {
    if (!throwTargetId) return;

    sendMessage({
        type: 'throw_card',
        data: {
            card: card,
            target_id: throwTargetId
        }
    });

    closeThrowModal();
    throwTargetId = null;
    throwTargetName = null;
    showNotification(`Threw ${card.rank} of ${card.suit}!`, 'throw');
}

function showPenaltyDialog() {
    if (!gameState || !gameState.players || gameState.players.length < 2) {
        showNotification('Need at least 2 players for penalties', 'error');
        return;
    }

    // Set default penalty cards
    document.getElementById('penalty-cards').value = defaultPenaltyCards;

    // If a player is already selected (from player action modal), use that player
    if (selectedPlayerId) {
        // Save to penaltyTargetId before it gets cleared
        penaltyTargetId = selectedPlayerId;
        penaltyTargetName = gameState.players.find(p => p.id === selectedPlayerId)?.name || 'Unknown';
        document.getElementById('penalty-target').textContent = penaltyTargetName;
        updatePenaltyReasonsSelect();
        document.getElementById('penalty-modal').classList.remove('hidden');
        return;
    }

    // Otherwise show modal with player list for selection
    const modal = document.getElementById('player-select-modal');
    const list = document.getElementById('player-select-list');

    const otherPlayers = gameState.players.filter(p => p.id !== playerId);
    list.innerHTML = otherPlayers.map(p => `
        <div class="player-select-item" onclick="selectPlayerForPenalty('${p.id}', '${p.name}')">
            <span class="player-name">${p.name}</span>
            <span class="player-cards">${p.card_count || 0} cards</span>
        </div>
    `).join('');

    modal.classList.remove('hidden');
}

function closePlayerSelectModal() {
    document.getElementById('player-select-modal').classList.add('hidden');
}

function selectPlayerForPenalty(id, name) {
    penaltyTargetId = id;
    penaltyTargetName = name;
    document.getElementById('player-select-modal').classList.add('hidden');
    document.getElementById('penalty-target').textContent = name;
    document.getElementById('penalty-cards').value = defaultPenaltyCards;
    updatePenaltyReasonsSelect();
    document.getElementById('penalty-modal').classList.remove('hidden');
}

function showPenaltyDialogForPlayer() {
    if (!selectedPlayerId) {
        showNotification('Click on a player first to give them a penalty', 'error');
        return;
    }

    // Save target BEFORE closing modal (like throw card does)
    penaltyTargetId = selectedPlayerId;
    penaltyTargetName = document.getElementById('player-action-name')?.textContent ||
        gameState?.players?.find(p => p.id === selectedPlayerId)?.name || 'Unknown';

    document.getElementById('penalty-target').textContent = penaltyTargetName;
    document.getElementById('penalty-cards').value = defaultPenaltyCards;

    updatePenaltyReasonsSelect();
    document.getElementById('penalty-modal').classList.remove('hidden');
    closePlayerModal();
}

function closePenaltyModal() {
    document.getElementById('penalty-modal').classList.add('hidden');
    document.getElementById('penalty-custom-reason').value = '';
}

function updatePenaltyReasonsSelect() {
    const select = document.getElementById('penalty-reason');
    select.innerHTML = '<option value="">Select a reason...</option>';

    penaltyReasons.forEach(reason => {
        const option = document.createElement('option');
        option.value = reason;
        option.textContent = reason;
        select.appendChild(option);
    });
}

function submitPenalty() {
    if (!penaltyTargetId) {
        showNotification('No target selected', 'error');
        return;
    }

    const reasonSelect = document.getElementById('penalty-reason');
    const customReason = document.getElementById('penalty-custom-reason').value.trim();
    const cards = parseInt(document.getElementById('penalty-cards').value) || 1;

    const reason = customReason || reasonSelect.value;
    if (!reason) {
        showNotification('Please select or enter a reason', 'error');
        return;
    }

    sendMessage({
        type: 'give_penalty',
        data: {
            target_id: penaltyTargetId,
            reason: reason,
            cards: cards
        }
    });

    closePenaltyModal();
    penaltyTargetId = null;  // Clear after submission
    penaltyTargetName = null;
}

// POO Actions
function viewMyHand() {
    viewingHand = true;
    sendMessage({ type: 'view_hand' });
    showNotification('Viewing your hand...', 'poo_action');
}

function toggleViewHand() {
    if (viewingHand) {
        // Already viewing, so hide
        viewingHand = false;
        document.getElementById('my-hand').style.display = 'none';
    } else {
        // Show hand
        viewingHand = true;
        document.getElementById('my-hand').style.display = 'flex';
        sendMessage({ type: 'view_hand' });
    }
}

function shuffleDeck() {
    sendMessage({ type: 'shuffle_cards' });
}

function endPoo() {
    sendMessage({ type: 'end_point_of_order' });
}

function showGameLog() {
    // Request game log from server
    sendMessage({ type: 'get_game_log' });
    // The server will send back the log, which we'll display
    document.getElementById('game-log-modal').classList.remove('hidden');
}

function closeGameLog() {
    document.getElementById('game-log-modal').classList.add('hidden');
}

function handleGameLog(data) {
    const logs = data.logs || data.data?.logs || [];
    const container = document.getElementById('game-log-content');
    container.innerHTML = '';

    if (logs.length === 0) {
        container.innerHTML = '<p>No events recorded yet.</p>';
        return;
    }

    logs.forEach(log => {
        const div = document.createElement('div');
        div.className = `log-entry log-${log.event_type}`;
        const time = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '';
        div.innerHTML = `<span class="log-time">${time}</span> <span class="log-player">${log.player_name || 'System'}</span>: ${log.details}`;
        container.appendChild(div);
    });

    container.scrollTop = container.scrollHeight;
}

function voteOnPenalty(index) {
    sendMessage({
        type: 'vote_penalty',
        data: { penalty_index: index }
    });
}

// Settings
function showSettingsModal() {
    renderPenaltyReasons();
    renderKeybinds();
    document.getElementById('default-penalty-cards').value = defaultPenaltyCards;
    // Show current avatar if exists
    const avatarPreview = document.getElementById('avatar-preview');
    const savedAvatar = safeGetRawItem('mao_avatar');
    if (savedAvatar && avatarPreview) {
        avatarPreview.src = savedAvatar;
    }
    document.getElementById('settings-modal').classList.remove('hidden');
}

// Avatar handling with crop modal
let avatarCropImage = null;      // Original image
let avatarCropZoom = 1;          // Current zoom level
let avatarCropOffsetX = 0;        // Pan offset X
let avatarCropOffsetY = 0;        // Pan offset Y
let avatarCropDragging = false;   // Is user dragging
let avatarCropLastX = 0;          // Last mouse X position
let avatarCropLastY = 0;          // Last mouse Y position
let avatarCropCanvas = null;      // Canvas element

function showAvatarCropModal(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Check file size (max 100KB)
    if (file.size > 100000) {
        showNotification('Avatar too large (max 100KB)', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            // Store image and reset crop state
            avatarCropImage = img;
            avatarCropZoom = 1;
            avatarCropOffsetX = 0;
            avatarCropOffsetY = 0;

            // Get canvas and set up
            avatarCropCanvas = document.getElementById('avatar-crop-canvas');
            avatarCropCanvas.width = 250;
            avatarCropCanvas.height = 250;

            // Set up drag events
            avatarCropCanvas.onmousedown = avatarCropStartDrag;
            avatarCropCanvas.onmousemove = avatarCropDrag;
            avatarCropCanvas.onmouseup = avatarCropEndDrag;
            avatarCropCanvas.onmouseleave = avatarCropEndDrag;
            avatarCropCanvas.onwheel = avatarCropWheel;

            // Render initial crop
            renderAvatarCrop();

            // Show modal
            document.getElementById('avatar-crop-modal').classList.remove('hidden');
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);

    // Clear file input so same file can be selected again
    event.target.value = '';
}

function avatarCropStartDrag(e) {
    avatarCropDragging = true;
    avatarCropLastX = e.clientX;
    avatarCropLastY = e.clientY;
    avatarCropCanvas.style.cursor = 'grabbing';
}

function avatarCropDrag(e) {
    if (!avatarCropDragging) return;

    const dx = e.clientX - avatarCropLastX;
    const dy = e.clientY - avatarCropLastY;

    avatarCropOffsetX += dx;
    avatarCropOffsetY += dy;

    avatarCropLastX = e.clientX;
    avatarCropLastY = e.clientY;

    renderAvatarCrop();
}

function avatarCropEndDrag() {
    avatarCropDragging = false;
    if (avatarCropCanvas) {
        avatarCropCanvas.style.cursor = 'grab';
    }
}

function avatarCropWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    avatarCropZoom = Math.max(0.5, Math.min(5, avatarCropZoom * delta));
    renderAvatarCrop();
}

function avatarCropZoomIn() {
    avatarCropZoom = Math.min(5, avatarCropZoom * 1.2);
    renderAvatarCrop();
}

function avatarCropZoomOut() {
    avatarCropZoom = Math.max(0.5, avatarCropZoom / 1.2);
    renderAvatarCrop();
}

function avatarCropReset() {
    avatarCropZoom = 1;
    avatarCropOffsetX = 0;
    avatarCropOffsetY = 0;
    renderAvatarCrop();
}

function renderAvatarCrop() {
    if (!avatarCropCanvas || !avatarCropImage) return;

    const ctx = avatarCropCanvas.getContext('2d');
    const canvasSize = 250;

    // Clear canvas
    ctx.clearRect(0, 0, canvasSize, canvasSize);

    // Calculate scaled dimensions
    const scaledWidth = avatarCropImage.width * avatarCropZoom;
    const scaledHeight = avatarCropImage.height * avatarCropZoom;

    // Center the image with offsets
    const centerX = canvasSize / 2 + avatarCropOffsetX;
    const centerY = canvasSize / 2 + avatarCropOffsetY;

    // Draw image centered
    ctx.drawImage(
        avatarCropImage,
        centerX - scaledWidth / 2,
        centerY - scaledHeight / 2,
        scaledWidth,
        scaledHeight
    );

    // Draw circular overlay guide
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(canvasSize / 2, canvasSize / 2, canvasSize / 2 - 5, 0, Math.PI * 2);
    ctx.stroke();
}

function applyAvatarCrop() {
    if (!avatarCropImage) return;

    const canvas = document.createElement('canvas');
    canvas.width = 100;
    canvas.height = 100;
    const ctx = canvas.getContext('2d');

    // Calculate source coordinates for circular crop
    const outputSize = 100;
    const canvasSize = 250;

    // Scale factor from display canvas to output
    const scale = outputSize / canvasSize;

    // Calculate the portion of the image visible in the circle
    const scaledWidth = avatarCropImage.width * avatarCropZoom;
    const scaledHeight = avatarCropImage.height * avatarCropZoom;

    // Center position on canvas
    const centerX = canvasSize / 2 + avatarCropOffsetX;
    const centerY = canvasSize / 2 + avatarCropOffsetY;

    // Convert to source image coordinates
    const srcX = (centerX - scaledWidth / 2) / avatarCropZoom;
    const srcY = (centerY - scaledHeight / 2) / avatarCropZoom;
    const srcWidth = scaledWidth / avatarCropZoom;
    const srcHeight = scaledHeight / avatarCropZoom;

    // Calculate crop size (square crop)
    const cropSize = Math.min(srcWidth, srcHeight);
    const cropX = srcX + (srcWidth - cropSize) / 2;
    const cropY = srcY + (srcHeight - cropSize) / 2;

    // Draw the cropped portion
    ctx.drawImage(
        avatarCropImage,
        cropX, cropY, cropSize, cropSize,
        0, 0, outputSize, outputSize
    );

    const avatar = canvas.toDataURL('image/jpeg', 0.9);
    safeSetRawItem('mao_avatar', avatar);
    document.getElementById('avatar-preview').src = avatar;

    // Send to server
    sendMessage({ type: 'update_avatar', data: { avatar: avatar } });
    showNotification('Avatar updated!', 'success');

    closeAvatarCropModal();
}

function closeAvatarCropModal() {
    document.getElementById('avatar-crop-modal').classList.add('hidden');
    avatarCropImage = null;
    avatarCropZoom = 1;
    avatarCropOffsetX = 0;
    avatarCropOffsetY = 0;
}

function clearAvatar() {
    safeSetRawItem('mao_avatar', '');
    document.getElementById('avatar-preview').src = '';
    sendMessage({ type: 'update_avatar', data: { avatar: null } });
    showNotification('Avatar cleared!', 'success');
}

// Player avatars storage
let playerAvatars = {};

function handleAvatarUpdate(data) {
    const playerId = data.player_id || data.data?.player_id;
    const avatar = data.avatar || data.data?.avatar;
    if (playerId) {
        if (avatar) {
            playerAvatars[playerId] = avatar;
        } else {
            delete playerAvatars[playerId];
        }
        // Re-render players to update avatars
        if (gameState) {
            updatePlayerPositions();
        }
    }
}

function renderKeybinds() {
    document.getElementById('keybind-draw').value = keybinds.draw.toUpperCase();
    document.getElementById('keybind-knock').value = keybinds.knock.toUpperCase();
    document.getElementById('keybind-mao').value = keybinds.mao.toUpperCase();
    document.getElementById('keybind-chat').value = keybinds.chat.toUpperCase();
}

function promptKeybind(action) {
    const input = document.getElementById(`keybind-${action}`);
    input.value = '...';
    input.focus();

    const handler = (e) => {
        e.preventDefault();
        const key = e.key.toLowerCase();
        if (key.length === 1 && /[a-z]/.test(key)) {
            keybinds[action] = key;
            input.value = key.toUpperCase();
            safeSetItem('mao_keybinds', keybinds);
        }
        document.removeEventListener('keydown', handler);
    };

    document.addEventListener('keydown', handler);
    input.onblur = () => {
        document.removeEventListener('keydown', handler);
        renderKeybinds();
    };
}

function resetKeybinds() {
    keybinds = { ...DEFAULT_KEYBINDS };
    safeSetItem('mao_keybinds', keybinds);
    renderKeybinds();
}

function saveDefaultPenaltyCards() {
    const input = document.getElementById('default-penalty-cards');
    defaultPenaltyCards = parseInt(input.value) || 2;
    safeSetRawItem('mao_penaltyCards', String(defaultPenaltyCards));
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
    safeSetItem('mao_penaltyReasons', penaltyReasons);
    updatePenaltyReasonsSelect();
}

function renderPenaltyReasons() {
    const container = document.getElementById('penalty-reasons-list');
    container.innerHTML = '';

    penaltyReasons.forEach((reason, index) => {
        const div = document.createElement('div');
        div.className = 'reason-item';
        div.innerHTML = `
            <span>${reason}</span>
            <button onclick="removePenaltyReason(${index})">Remove</button>
        `;
        container.appendChild(div);
    });
}

function addPenaltyReason() {
    const input = document.getElementById('new-reason');
    const reason = input.value.trim();

    if (reason && !penaltyReasons.includes(reason)) {
        penaltyReasons.push(reason);
        renderPenaltyReasons();
        input.value = '';
    }
}

function removePenaltyReason(index) {
    penaltyReasons.splice(index, 1);
    renderPenaltyReasons();
}

// UI Helpers
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.add('hidden'));
    const screen = document.getElementById(`${screenId}-screen`);
    if (screen) {
        screen.classList.remove('hidden');
    }
}

function showStatus(message, type) {
    const status = document.getElementById('connection-status');
    if (status) {
        status.textContent = message;
        status.className = `status ${type}`;
    }
}

function showNotification(message, type = 'default') {
    const container = document.getElementById('notifications');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `notification ${type}`;
    div.textContent = message;
    container.appendChild(div);

    // Auto-scroll
    container.scrollTop = container.scrollHeight;

    // Auto-remove after 10 seconds
    setTimeout(() => {
        div.remove();
    }, 10000);
}

// Keyboard shortcuts - only work when game is in progress
document.addEventListener('keydown', (e) => {
    // Don't trigger shortcuts when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Only allow shortcuts when game is active
    if (!gameState || (gameState.phase !== 'in_progress' && gameState.phase !== 'point_of_order')) {
        return;
    }

    const key = e.key.toLowerCase();

    if (key === keybinds.draw) {
        e.preventDefault();
        drawCard();
    } else if (key === keybinds.knock) {
        e.preventDefault();
        sendKnock();
    } else if (key === keybinds.mao) {
        e.preventDefault();
        declareMao();
    } else if (key === keybinds.chat) {
        e.preventDefault();
        document.getElementById('chat-input').focus();
    }
});

// Close modals on outside click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });
});

// Chat input enter key handler
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
});

// Make functions globally available
window.connect = connect;
window.drawCard = drawCard;
window.sendKnock = sendKnock;
window.showSayDialog = showSayDialog;
window.closeSayModal = closeSayModal;
window.sendSay = sendSay;
window.declareMao = declareMao;
window.challengeMao = challengeMao;
window.startGame = startGame;
window.leaveGame = leaveGame;
window.showPlayerActions = showPlayerActions;
window.closePlayerModal = closePlayerModal;
window.hitPlayer = hitPlayer;
window.showThrowCardDialog = showThrowCardDialog;
window.closeThrowModal = closeThrowModal;
window.throwCard = throwCard;
window.showPenaltyDialog = showPenaltyDialog;
window.showPenaltyDialogForPlayer = showPenaltyDialogForPlayer;
window.closePenaltyModal = closePenaltyModal;
window.submitPenalty = submitPenalty;
window.viewMyHand = viewMyHand;
window.shuffleDeck = shuffleDeck;
window.endPoo = endPoo;
window.showPooModal = showPooModal;
window.closePooModal = closePooModal;
window.voteOnPenalty = voteOnPenalty;
window.castVote = castVote;
window.showSettingsModal = showSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.addPenaltyReason = addPenaltyReason;
window.removePenaltyReason = removePenaltyReason;
window.promptKeybind = promptKeybind;
window.resetKeybinds = resetKeybinds;
window.saveDefaultPenaltyCards = saveDefaultPenaltyCards;
window.playCard = playCard;
window.toggleViewHand = toggleViewHand;
window.closeJoinModal = closeJoinModal;
window.confirmJoinLobby = confirmJoinLobby;
window.showJoinModal = showJoinModal;
window.createLobby = createLobby;
window.requestLobbyList = requestLobbyList;
window.leaveLobby = leaveLobby;
window.toggleCommandMenu = toggleCommandMenu;
window.toggleChat = toggleChat;
window.sendChatMessage = sendChatMessage;
window.closePlayerSelectModal = closePlayerSelectModal;
window.selectPlayerForPenalty = selectPlayerForPenalty;
window.showGameLog = showGameLog;
window.closeGameLog = closeGameLog;
window.showAvatarCropModal = showAvatarCropModal;
window.avatarCropZoomIn = avatarCropZoomIn;
window.avatarCropZoomOut = avatarCropZoomOut;
window.avatarCropReset = avatarCropReset;
window.applyAvatarCrop = applyAvatarCrop;
window.closeAvatarCropModal = closeAvatarCropModal;