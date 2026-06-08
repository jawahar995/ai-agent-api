const { Room, RoomEvent } = LivekitClient;

// DOM Elements
const setupPane = document.getElementById('setup-pane');
const chatPane = document.getElementById('chat-pane');
const connectForm = document.getElementById('connect-form');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const messagesBox = document.getElementById('messages-box');

const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');

const activeRoomName = document.getElementById('active-room-name');
const activeUserName = document.getElementById('active-user-name');

const btnDisconnect = document.getElementById('btn-disconnect');
const btnConnect = document.getElementById('btn-connect');

let currentRoom = null;

// Connect Event
connectForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const roomName = document.getElementById('room-name').value.trim();
    const participantName = document.getElementById('participant-name').value.trim();

    if (!roomName || !participantName) return;

    updateStatus('connecting', 'Connecting...');
    btnConnect.disabled = true;
    btnConnect.textContent = 'Connecting...';

    try {
        // 1. Fetch connection details from the backend
        const response = await fetch('http://localhost:8000/agent/create/6a16c71d845e04d1af8c2799', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                room_name: roomName,
                participant_name: participantName
            })
        });

        if (!response.ok) {
            throw new Error(`Token generation failed: ${response.statusText}`);
        }

        const data = await response.json();
        const { token, server_url } = data;

        // 2. Instantiate and configure Room
        currentRoom = new Room({
            adaptiveStream: true,
            dynacast: true,
        });

        // Setup room event listeners
        currentRoom
            .on(RoomEvent.Connected, () => {
                updateStatus('connected', 'Connected');
                setupPane.classList.add('hidden');
                chatPane.classList.remove('hidden');
                activeRoomName.textContent = roomName;
                activeUserName.textContent = participantName;

                messagesBox.innerHTML = ''; // Clear previous messages
                addSystemMessage(`Successfully connected to room "${roomName}". Waiting for agent...`);
            })
            .on(RoomEvent.Disconnected, (reason) => {
                cleanupRoom();
                addSystemMessage(`Disconnected from room. Reason: ${reason || 'User initiated'}`);
            })
            .on(RoomEvent.ParticipantConnected, (participant) => {
                addSystemMessage(`Participant joined: ${participant.identity}`);
            })
            .on(RoomEvent.ParticipantDisconnected, (participant) => {
                addSystemMessage(`Participant left: ${participant.identity}`);
            });

        // Track active message streams to update in real-time
        const activeStreams = {};

        function handleIncomingText(senderName, text) {
            // Check if this is a streaming JSON packet
            try {
                const data = JSON.parse(text);
                if (data && data.type === 'chat_chunk') {
                    const { message_id, content, done } = data;
                    if (!activeStreams[message_id]) {
                        // Create a new message bubble
                        const msgDiv = document.createElement('div');
                        msgDiv.className = 'message agent';

                        const senderSpan = document.createElement('span');
                        senderSpan.className = 'msg-sender';
                        senderSpan.textContent = senderName;

                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'msg-content';
                        contentDiv.textContent = content;

                        msgDiv.appendChild(senderSpan);
                        msgDiv.appendChild(contentDiv);

                        messagesBox.appendChild(msgDiv);
                        messagesBox.scrollTop = messagesBox.scrollHeight;

                        activeStreams[message_id] = {
                            element: contentDiv,
                            fullText: content
                        };
                    } else {
                        // Append text to existing bubble
                        const stream = activeStreams[message_id];
                        stream.fullText += content;
                        stream.element.textContent = stream.fullText;
                        messagesBox.scrollTop = messagesBox.scrollHeight;
                    }

                    if (done) {
                        delete activeStreams[message_id];
                    }
                    return;
                }
            } catch (e) {
                // Not valid JSON or doesn't have type 'chat_chunk', fallback to raw message
            }

            // Deduplicate incoming raw text (e.g. if received via both DataReceived and TextReceived)
            const dedupeKey = `${senderName}:${text}`;
            if (window.lastReceivedMessageKey === dedupeKey) {
                return;
            }
            window.lastReceivedMessageKey = dedupeKey;
            setTimeout(() => {
                if (window.lastReceivedMessageKey === dedupeKey) {
                    window.lastReceivedMessageKey = null;
                }
            }, 1000);

            addMessage('agent', senderName, text);
        }

        // Listen for incoming data packets (chat messages)
        currentRoom.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
            console.log("Received DataReceived event:", { payload, participant, kind, topic });

            // Ignore messages sent by ourselves
            if (participant && participant.identity === currentRoom.localParticipant.identity) {
                return;
            }

            const text = new TextDecoder().decode(payload);
            handleIncomingText(participant ? participant.identity : 'Agent', text);
        });

        // Support for newer textReceived event format if available
        if (RoomEvent.TextReceived) {
            currentRoom.on(RoomEvent.TextReceived, (text, participant, info) => {
                console.log("Received TextReceived event:", { text, participant, info });

                // Ignore messages sent by ourselves
                if (participant && participant.identity === currentRoom.localParticipant.identity) {
                    return;
                }

                handleIncomingText(participant ? participant.identity : 'Agent', text);
            });
        }

        // 3. Connect to the room
        // Check if the URL needs to use WebSocket protocol
        let connectUrl = server_url;
        if (connectUrl.startsWith('http://')) {
            connectUrl = connectUrl.replace('http://', 'ws://');
        } else if (connectUrl.startsWith('https://')) {
            connectUrl = connectUrl.replace('https://', 'wss://');
        }

        await currentRoom.connect(connectUrl, token);

    } catch (err) {
        console.error('Failed to connect:', err);
        alert(`Error connecting to Room: ${err.message}`);
        updateStatus('disconnected', 'Disconnected');
        btnConnect.disabled = false;
        btnConnect.textContent = 'Connect to Room';
    }
});

// Disconnect Button
btnDisconnect.addEventListener('click', async () => {
    if (currentRoom) {
        await currentRoom.disconnect();
    }
});

// Chat Submit Event
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text || !currentRoom) return;

    chatInput.value = '';

    // Add user message to UI immediately
    addMessage('user', 'You', text);

    try {
        const encoder = new TextEncoder();
        const payload = encoder.encode(text);

        // Publish chat data packet to the room
        try {
            await currentRoom.localParticipant.publishData(payload, {
                topic: 'lk-chat-topic',
                reliable: true
            });
        } catch (err) {
            // Fallback for older LiveKit client SDK signatures
            await currentRoom.localParticipant.publishData(payload, 1, {
                topic: 'lk-chat-topic'
            });
        }
    } catch (err) {
        console.error('Failed to send message:', err);
        addSystemMessage(`Error sending message: ${err.message}`);
    }
});

// UI Helpers
function updateStatus(state, text) {
    statusDot.className = `dot ${state}`;
    statusText.textContent = text;
}

function cleanupRoom() {
    currentRoom = null;
    updateStatus('disconnected', 'Disconnected');
    setupPane.classList.remove('hidden');
    chatPane.classList.add('hidden');

    btnConnect.disabled = false;
    btnConnect.textContent = 'Connect to Room';
}

function addMessage(senderType, senderName, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${senderType}`;

    const senderSpan = document.createElement('span');
    senderSpan.className = 'msg-sender';
    senderSpan.textContent = senderName;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'msg-content';
    contentDiv.textContent = text;

    msgDiv.appendChild(senderSpan);
    msgDiv.appendChild(contentDiv);

    messagesBox.appendChild(msgDiv);
    messagesBox.scrollTop = messagesBox.scrollHeight;
}

function addSystemMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system-msg';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'msg-content';
    contentDiv.textContent = text;

    msgDiv.appendChild(contentDiv);

    messagesBox.appendChild(msgDiv);
    messagesBox.scrollTop = messagesBox.scrollHeight;
}
