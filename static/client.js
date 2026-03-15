// Mao Card Game - WebSocket Client

let ws = null;
let playerId = null;
let playerName = null;
let gameState = null;
let myHand = [];
let selectedPlayerId = null;
let viewingHand = false;
let pooActive = false;

// Penalty reasons (stored in localStorage)
let penaltyReasons = JSON.parse(localStorage.getItem('mao_penaltyReasons')) || [
    'Wrong play',
    'Failure to knock',
    'Speaking out of turn',
    'Touching cards during POO',
    'Looking at cards during play'
];

// Card suit symbols
const SUIT_SYMBOLS = {
    'hearts': '♥',
    'diamonds': '♦',
    'clubs': '♣',
    'spades': '♠'
};

// Message type handlers
const messageHandlers = {
    'connect': handleConnect,
    'player_list': handlePlayerList,
    'game_state': handleGameState,
    'hand_update': handleHandUpdate,
    'card_drawn': handleCardDrawn,
    'penalty': handlePenalty,
    'notification': handleNotification,
    'point_of_order': handlePointOfOrder,
    'game_over': handleGameOver,
    'error': handleError,
    'success': handleSuccess
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('connect-btn').addEventListener('click', connect);
    document.getElementById('player-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') connect();
    });
    document.getElementById('start-btn').addEventListener('click', startGame);
    document.getElementById('leave-btn').addEventListener('click', leaveGame);
    document.getElementById('settings-btn').addEventListener('click', showSettingsModal);

    // Populate penalty reasons
    updatePenaltyReasonsSelect();
});

// Connection
function connect() {
    const nameInput = document.getElementById('player-name');
    playerName = nameInput.value.trim();

    if (!playerName) {
        showStatus('Please enter your name', 'error');
        return;
    }

    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        showStatus('Connected!', 'success');
        sendMessage({
            type: 'connect',
            data: { name: playerName }
        });
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

// Message Handlers
function handleConnect(data) {
    playerId = data.player_id || data.data?.player_id;
    const name = data.name || data.data?.name || playerName;
    showScreen('lobby');
    showStatus(`Connected as ${name}`, 'success');

    // Join the game
    sendMessage({ type: 'join_game' });
}

function handlePlayerList(data) {
    const players = data.players || data.data?.players || [];
    updatePlayerListDisplay(players, 'lobby');
}

function handleGameState(data) {
    gameState = data.data || data;
    console.log('Game state:', gameState);

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

    // Update draw pile count
    document.getElementById('draw-count').textContent = gameState.draw_pile_count || 0;

    // Update recent cards
    updateRecentCards();

    // Update hand
    renderHand();
}

function updatePlayerPositions() {
    const container = document.getElementById('other-players');
    container.innerHTML = '';

    if (!gameState || !gameState.players) return;

    // Get other players (not me)
    const otherPlayers = gameState.players.filter(p => p.id !== playerId);

    // Position other players around the center
    // For N players, distribute evenly in top/left/right positions
    otherPlayers.forEach((player, index) => {
        const div = document.createElement('div');
        div.className = 'player-slot';

        if (gameState.current_player_id === player.id) {
            div.classList.add('current-turn');
        }

        // Simple positioning: distribute around the center
        // Positions: top, top-right, right, left, top-left, etc.
        const total = otherPlayers.length;
        const positions = getPlayerPositions(total);
        const pos = positions[index];

        div.style.left = pos.left;
        div.style.top = pos.top;
        div.style.transform = 'translate(-50%, -50%)';

        const avatar = document.createElement('div');
        avatar.className = 'player-avatar';
        avatar.textContent = player.name.charAt(0).toUpperCase();

        const nameDiv = document.createElement('div');
        nameDiv.className = 'player-name';
        nameDiv.textContent = player.name;

        const countDiv = document.createElement('div');
        countDiv.className = 'player-card-count';
        countDiv.textContent = `${player.card_count || 0} cards`;

        div.appendChild(avatar);
        div.appendChild(nameDiv);
        div.appendChild(countDiv);

        // Click to show actions
        div.addEventListener('click', () => showPlayerActions(player));

        container.appendChild(div);
    });
}

function getPlayerPositions(count) {
    // Generate positions around the center, avoiding bottom (reserved for me)
    // Returns array of {left, top} as percentages
    const positions = [];

    // Spread players evenly in the upper portion of the screen
    // Angles from -150 to -30 degrees (top left to top right)
    for (let i = 0; i < count; i++) {
        const angle = -150 + (120 / Math.max(count - 1, 1)) * i;
        const radians = angle * Math.PI / 180;

        // Use 40% radius from center
        const radius = 40;
        const centerX = 50;
        const centerY = 35;

        const x = centerX + radius * Math.cos(radians);
        const y = centerY + radius * Math.sin(radians);

        positions.push({
            left: `${x}%`,
            top: `${y}%`
        });
    }

    return positions;
}

function updateDiscardPile() {
    const topCardDiv = document.getElementById('top-card');

    // Try recent_cards first, then top_card
    let topCard = null;
    if (gameState.recent_cards && gameState.recent_cards.length > 0) {
        topCard = gameState.recent_cards[gameState.recent_cards.length - 1];
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
    container.innerHTML = '';

    if (!gameState.recent_cards || gameState.recent_cards.length <= 1) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';

    // Show last 3 plays (excluding current top card)
    const recent = gameState.recent_cards.slice(0, -1).slice(-3).reverse();
    recent.forEach(card => {
        const div = document.createElement('div');
        div.className = 'recent-card';
        const suit = SUIT_SYMBOLS[card.suit.toLowerCase()] || card.suit;
        div.textContent = `${card.rank}${suit}`;
        container.appendChild(div);
    });
}

function updateKeyboardShortcuts() {
    // Keyboard shortcuts only work when game is in progress
}

function renderCard(container, card) {
    container.innerHTML = '';

    const suitSymbol = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';

    // Try to use card image first
    const rank = (card.rank || card.Rank || '').toString().toLowerCase();
    const suit = (card.suit || card.Suit || '').toLowerCase();

    if (rank && suit) {
        const cardName = `${rank}_of_${suit}`;
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
        cardDiv.innerHTML = `
            <span class="rank">${card.rank || card.Rank || '?'}</span>
            <span class="suit-symbol">${suitSymbol}</span>
        `;

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
}

function handlePointOfOrder(data) {
    pooActive = true;
    document.body.classList.add('poo-active');
    document.getElementById('poo-indicator').classList.remove('hidden');

    const reason = data.reason || data.data?.reason || 'No reason given';
    const caller = data.caller_name || data.data?.caller_name || 'Someone';
    document.getElementById('poo-reason').textContent = reason;
    document.getElementById('poo-caller').textContent = caller;

    // Show POO modal with penalty history
    const pooModal = document.getElementById('poo-modal');

    // Update penalty history
    const penaltyHistory = data.penalty_history || data.data?.penalty_history || [];
    const penaltyList = document.getElementById('penalty-list');
    penaltyList.innerHTML = '';

    if (penaltyHistory.length === 0) {
        penaltyList.innerHTML = '<p>No penalties yet</p>';
    } else {
        penaltyHistory.forEach((penalty, index) => {
            const div = document.createElement('div');
            div.className = 'penalty-item' + (penalty.overturned ? ' overturned' : '');
            div.innerHTML = `${index + 1}. ${penalty.caller_name} → ${penalty.target_name}: ${penalty.reason} (${penalty.cards} cards)`;
            div.onclick = () => voteOnPenalty(index);
            penaltyList.appendChild(div);
        });
    }

    pooModal.classList.remove('hidden');
}

function activatePooMode() {
    pooActive = true;
    document.body.classList.add('poo-active');
    document.getElementById('poo-indicator').classList.remove('hidden');
    document.getElementById('view-hand-btn').classList.remove('hidden');
}

function deactivatePooMode() {
    pooActive = false;
    document.body.classList.remove('poo-active');
    document.getElementById('poo-indicator').classList.add('hidden');
    document.getElementById('poo-modal').classList.add('hidden');
    document.getElementById('view-hand-btn').classList.add('hidden');
    viewingHand = false;
}

function handleGameOver(data) {
    const winnerName = data.winner_name || data.data?.winner_name || 'Unknown';
    const winnerId = data.winner_id || data.data?.winner_id;
    const cardCount = data.card_count || data.data?.card_count || 0;

    const modal = document.getElementById('game-over-modal');
    const winnerText = winnerId === playerId
        ? `🎉 You win with ${cardCount} cards remaining! 🎉`
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
    showNotification(`Hit sent!`, 'hit');
}

function showThrowCardDialog() {
    if (!selectedPlayerId) return;

    const targetName = document.getElementById('player-action-name').textContent;
    document.getElementById('throw-target-name').textContent = targetName;
    document.getElementById('throw-card-modal').classList.remove('hidden');

    // Show cards from hand
    const throwHand = document.getElementById('throw-hand');
    throwHand.innerHTML = '';

    myHand.forEach((card, index) => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${(card.suit || '').toLowerCase()}`;
        const suitSymbol = SUIT_SYMBOLS[card.suit?.toLowerCase()] || card.suit || '';
        cardDiv.innerHTML = `
            <span class="rank">${card.rank || '?'}</span>
            <span class="suit-symbol">${suitSymbol}</span>
        `;
        cardDiv.onclick = () => throwCard(card);
        throwHand.appendChild(cardDiv);
    });

    closePlayerModal();
}

function closeThrowModal() {
    document.getElementById('throw-card-modal').classList.add('hidden');
}

function throwCard(card) {
    if (!selectedPlayerId) return;

    sendMessage({
        type: 'throw_card',
        data: {
            card: card,
            target_id: selectedPlayerId
        }
    });

    closeThrowModal();
    showNotification(`Threw ${card.rank} of ${card.suit}!`, 'throw');
}

function showPenaltyDialog() {
    showPenaltyDialogForPlayer();
}

function showPenaltyDialogForPlayer() {
    if (!selectedPlayerId) {
        showNotification('Click on a player first to give them a penalty', 'error');
        return;
    }

    const targetName = document.getElementById('player-action-name')?.textContent ||
        gameState?.players?.find(p => p.id === selectedPlayerId)?.name || 'Unknown';
    document.getElementById('penalty-target').textContent = targetName;

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
    if (!selectedPlayerId) {
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
            target_id: selectedPlayerId,
            reason: reason,
            cards: cards
        }
    });

    closePenaltyModal();
}

// POO Actions
function viewMyHand() {
    viewingHand = true;
    sendMessage({ type: 'view_hand' });
    showNotification('Viewing your hand...', 'poo_action');
}

function shuffleDeck() {
    sendMessage({ type: 'shuffle_cards' });
}

function endPoo() {
    sendMessage({ type: 'end_point_of_order' });
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
    document.getElementById('settings-modal').classList.remove('hidden');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
    localStorage.setItem('mao_penaltyReasons', JSON.stringify(penaltyReasons));
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
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Only allow shortcuts when game is active
    if (!gameState || (gameState.phase !== 'in_progress' && gameState.phase !== 'point_of_order')) {
        return;
    }

    switch (e.key.toLowerCase()) {
        case 'd':
            drawCard();
            break;
        case 'k':
            sendKnock();
            break;
        case 'm':
            declareMao();
            break;
        case 's':
            showSayDialog();
            break;
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

// Make functions globally available
window.connect = connect;
window.drawCard = drawCard;
window.sendKnock = sendKnock;
window.showSayDialog = showSayDialog;
window.closeSayModal = closeSayModal;
window.sendSay = sendSay;
window.declareMao = declareMao;
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
window.voteOnPenalty = voteOnPenalty;
window.showSettingsModal = showSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.addPenaltyReason = addPenaltyReason;
window.removePenaltyReason = removePenaltyReason;
window.playCard = playCard;