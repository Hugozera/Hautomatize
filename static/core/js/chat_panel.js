(function () {
    'use strict';

    function getCookie(name) {
        const value = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return value ? value[2] : null;
    }

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatTime(isoText) {
        if (!isoText) return '';
        try {
            return new Date(isoText).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return '';
        }
    }

    function debounce(fn, delay) {
        let timer = null;
        return function () {
            const args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(null, args);
            }, delay);
        };
    }

    function initChatPanel() {
        const chatBubble = document.getElementById('chatBubble');
        const panel = document.getElementById('globalChatPanel');
        const content = document.getElementById('chat-content');
        const input = document.getElementById('chat-input');
        const send = document.getElementById('chat-send');
        const closeBtn = document.getElementById('chat-close');

        if (!chatBubble || !panel || !content || !input || !send || !closeBtn) {
            return;
        }

        if (chatBubble.dataset.chatInitialized === '1') {
            return;
        }
        chatBubble.dataset.chatInitialized = '1';

        let panelVisible = false;
        let activeRoomId = null;
        let activeConversationId = null;
        let activeSocket = null;
        let typingTimer = null;
        let typingState = false;
        let allConversations = [];
        let allUsers = [];

        content.classList.add('hp-chat-root');

        function renderShell() {
            content.innerHTML = '';
            content.innerHTML = [
                '<div class="hp-chat-layout">',
                '  <aside class="hp-chat-sidebar">',
                '    <div class="hp-sidebar-top">',
                '      <input id="hp-search" class="hp-search" type="text" placeholder="Buscar conversas..." />',
                '      <button id="hp-new-chat" class="hp-new-chat" type="button">Novo chat</button>',
                '    </div>',
                '    <div id="hp-users-box" class="hp-users-box" style="display:none;"></div>',
                '    <div id="hp-conversations" class="hp-conversations"></div>',
                '  </aside>',
                '  <section class="hp-chat-main">',
                '    <div id="hp-main-head" class="hp-main-head">',
                '      <div class="hp-main-title">Selecione uma conversa</div>',
                '      <div id="hp-main-presence" class="hp-main-presence"></div>',
                '    </div>',
                '    <div id="hp-main-messages" class="hp-main-messages">',
                '      <div class="chat-empty">',
                '        <div class="chat-empty-icon">💬</div>',
                '        <div class="chat-empty-text">Escolha alguém para conversar</div>',
                '      </div>',
                '    </div>',
                '    <div id="hp-typing-indicator" class="hp-typing-indicator" style="display:none;">Digitando...</div>',
                '  </section>',
                '</div>'
            ].join('');
        }

        function sidebarElements() {
            return {
                searchInput: document.getElementById('hp-search'),
                newChatBtn: document.getElementById('hp-new-chat'),
                usersBox: document.getElementById('hp-users-box'),
                conversationsEl: document.getElementById('hp-conversations'),
                mainTitle: document.querySelector('#hp-main-head .hp-main-title'),
                mainPresence: document.getElementById('hp-main-presence'),
                mainMessages: document.getElementById('hp-main-messages'),
                typingIndicator: document.getElementById('hp-typing-indicator')
            };
        }

        function setComposerEnabled(enabled) {
            input.disabled = !enabled;
            send.disabled = !enabled;
            input.placeholder = enabled ? 'Digite sua mensagem...' : 'Selecione uma conversa para enviar';
        }

        function clearChatBadge() {
            const bubbleBadge = document.querySelector('#chatBubble .chat-badge');
            if (bubbleBadge) {
                bubbleBadge.textContent = '0';
                bubbleBadge.style.display = 'none';
            }
        }
        window.clearChatBadge = clearChatBadge;

        function conversationTitle(conv) {
            if (!conv) return 'Conversa';
            return conv.title || 'Conversa';
        }

        function normalizeConversation(conv) {
            return {
                id: conv.id,
                roomId: 'conv-' + conv.id,
                title: conversationTitle(conv),
                lastMessage: conv.last_message || '',
                lastTime: conv.last_time || '',
                participants: conv.participants || []
            };
        }

        function renderConversations(filterText) {
            const { conversationsEl } = sidebarElements();
            if (!conversationsEl) return;

            const query = String(filterText || '').trim().toLowerCase();
            const list = allConversations
                .map(normalizeConversation)
                .filter(function (item) {
                    if (!query) return true;
                    return item.title.toLowerCase().includes(query) ||
                        item.lastMessage.toLowerCase().includes(query);
                });

            if (!list.length) {
                conversationsEl.innerHTML = '<div class="chat-empty"><div class="chat-empty-text">Nenhuma conversa encontrada</div></div>';
                return;
            }

            conversationsEl.innerHTML = list.map(function (conv) {
                const activeClass = activeRoomId === conv.roomId ? ' active' : '';
                return [
                    '<div class="chat-conversation-item' + activeClass + '" data-id="' + escapeHtml(conv.roomId) + '" data-room-id="' + escapeHtml(conv.roomId) + '">',
                    '  <div class="chat-avatar">' + escapeHtml((conv.title || 'C').charAt(0).toUpperCase()) + '</div>',
                    '  <div class="chat-contact-info">',
                    '    <div class="chat-contact-name">' + escapeHtml(conv.title) + '</div>',
                    '    <div class="chat-contact-preview">' + escapeHtml(conv.lastMessage || 'Sem mensagens ainda') + '</div>',
                    '  </div>',
                    '  <div class="chat-conversation-meta">' + escapeHtml(formatTime(conv.lastTime)) + '</div>',
                    '</div>'
                ].join('');
            }).join('');

            conversationsEl.querySelectorAll('.chat-conversation-item').forEach(function (item) {
                item.addEventListener('click', function () {
                    const roomId = item.getAttribute('data-room-id');
                    const conv = allConversations.find(function (c) {
                        return ('conv-' + c.id) === roomId;
                    });
                    openRoom(roomId, conv ? conversationTitle(conv) : 'Conversa');
                });
            });
        }

        function renderUsers(users) {
            const { usersBox } = sidebarElements();
            if (!usersBox) return;

            if (!users || !users.length) {
                usersBox.innerHTML = '<div class="chat-empty"><div class="chat-empty-text">Nenhum usuário disponível</div></div>';
                return;
            }

            usersBox.innerHTML = users.slice(0, 80).map(function (user) {
                const name = user.name || user.username || ('Usuário ' + user.id);
                return [
                    '<button type="button" class="hp-user-item" data-user-id="' + escapeHtml(user.id) + '" data-user-name="' + escapeHtml(name) + '">',
                    '  <span class="chat-avatar">' + escapeHtml(name.charAt(0).toUpperCase()) + '</span>',
                    '  <span class="chat-contact-info">',
                    '    <span class="chat-contact-name">' + escapeHtml(name) + '</span>',
                    '    <span class="chat-contact-preview">Iniciar conversa</span>',
                    '  </span>',
                    '</button>'
                ].join('');
            }).join('');

            usersBox.querySelectorAll('.hp-user-item').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const userId = parseInt(btn.getAttribute('data-user-id') || '0', 10);
                    const userName = btn.getAttribute('data-user-name') || 'Conversa';
                    createConversationWithUser(userId, userName);
                });
            });
        }

        function fetchUsers() {
            return fetch('/api/users/')
                .then(function (response) { return response.json(); })
                .then(function (json) {
                    allUsers = json.users || [];
                    return allUsers;
                })
                .catch(function () {
                    allUsers = [];
                    return [];
                });
        }

        function fetchConversations() {
            return fetch('/chat/my_conversations/')
                .then(function (response) { return response.json(); })
                .then(function (json) {
                    allConversations = json.conversations || [];
                    return allConversations;
                })
                .catch(function () {
                    allConversations = [];
                    return [];
                });
        }

        function markRoomRead(roomId) {
            if (!roomId || !roomId.startsWith('conv-')) return;
            const conversationId = parseInt(roomId.split('-')[1], 10);
            if (!conversationId) return;
            fetch('/chat/mark_read/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ conversation_id: conversationId })
            }).catch(function () { });
        }

        function showTyping(isTyping, username) {
            const { typingIndicator } = sidebarElements();
            if (!typingIndicator) return;
            if (!isTyping) {
                typingIndicator.style.display = 'none';
                typingIndicator.textContent = 'Digitando...';
                return;
            }
            typingIndicator.textContent = (username || 'Alguém') + ' está digitando...';
            typingIndicator.style.display = 'block';
            setTimeout(function () {
                typingIndicator.style.display = 'none';
            }, 2200);
        }

        function appendMessage(messageData) {
            const { mainMessages } = sidebarElements();
            if (!mainMessages) return;

            const own = !!messageData.own || (window.userName && messageData.user === window.userName);
            const wrapper = document.createElement('div');
            wrapper.className = 'chat-message ' + (own ? 'sent' : 'received');

            const bubble = document.createElement('div');
            bubble.className = 'chat-message-bubble';
            bubble.textContent = messageData.message || '';

            const time = document.createElement('div');
            time.className = 'chat-message-time';
            time.textContent = messageData.time || formatTime(messageData.created) || '';

            wrapper.appendChild(bubble);
            wrapper.appendChild(time);
            mainMessages.appendChild(wrapper);
            mainMessages.scrollTop = mainMessages.scrollHeight;
        }

        function renderHistory(messages) {
            const { mainMessages } = sidebarElements();
            if (!mainMessages) return;
            mainMessages.innerHTML = '';

            if (!messages || !messages.length) {
                mainMessages.innerHTML = '<div class="chat-empty"><div class="chat-empty-text">Nenhuma mensagem ainda. Envie a primeira.</div></div>';
                return;
            }

            messages.forEach(appendMessage);
        }

        function updateMainHeader(titleText, presenceText) {
            const { mainTitle, mainPresence } = sidebarElements();
            if (mainTitle) mainTitle.textContent = titleText || 'Conversa';
            if (mainPresence) mainPresence.textContent = presenceText || '';
        }

        function connectRoomSocket(roomId) {
            if (activeSocket) {
                try {
                    activeSocket.close();
                } catch (e) {
                }
            }

            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = protocol + window.location.host + '/ws/chat/' + roomId + '/';
            activeSocket = new WebSocket(wsUrl);

            activeSocket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'typing') {
                        const sameUser = window.userName && data.user && data.user === window.userName;
                        if (!sameUser) showTyping(!!data.typing, data.user);
                        return;
                    }
                    if (data.type === 'presence') {
                        const onlineCount = Array.isArray(data.users) ? data.users.length : 0;
                        updateMainHeader(undefined, onlineCount > 0 ? onlineCount + ' online' : '');
                        return;
                    }
                    if (data.type === 'message' || data.type === 'chat_message' || data.message) {
                        appendMessage({
                            user: data.user,
                            message: data.message,
                            created: data.created,
                            time: formatTime(data.created),
                            own: !!(window.userName && data.user === window.userName)
                        });
                        fetchConversations().then(function () {
                            renderConversations((sidebarElements().searchInput || {}).value || '');
                        });
                    }
                } catch (e) {
                }
            };
        }

        function openRoom(roomId, titleText) {
            activeRoomId = roomId;
            activeConversationId = roomId.startsWith('conv-') ? parseInt(roomId.split('-')[1], 10) : null;
            setComposerEnabled(true);
            updateMainHeader(titleText || 'Conversa', '');
            showTyping(false);

            renderConversations((sidebarElements().searchInput || {}).value || '');

            fetch('/api/messages/' + encodeURIComponent(roomId) + '/')
                .then(function (response) { return response.json(); })
                .then(function (messages) {
                    renderHistory(messages || []);
                })
                .catch(function () {
                    renderHistory([]);
                });

            connectRoomSocket(roomId);
            clearChatBadge();
            markRoomRead(roomId);
        }

        function createConversationWithUser(userId, userName) {
            if (!userId) return;

            fetch('/chat/create_user_conversation/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_id: userId })
            })
                .then(function (response) { return response.json(); })
                .then(function (json) {
                    if (!json || !json.conversation_id) return;
                    const roomId = 'conv-' + json.conversation_id;
                    fetchConversations().then(function () {
                        const { usersBox } = sidebarElements();
                        if (usersBox) usersBox.style.display = 'none';
                        renderConversations((sidebarElements().searchInput || {}).value || '');
                        openRoom(roomId, userName || 'Conversa');
                    });
                })
                .catch(function () {
                });
        }

        function refreshList() {
            return fetchConversations().then(function () {
                renderConversations((sidebarElements().searchInput || {}).value || '');
            });
        }

        function showPanel() {
            panel.classList.add('show');
            panelVisible = true;
            clearChatBadge();
            setComposerEnabled(false);
            renderShell();

            Promise.all([fetchConversations(), fetchUsers()]).then(function () {
                const elements = sidebarElements();
                renderConversations('');
                renderUsers(allUsers);

                if (elements.searchInput) {
                    const onSearch = debounce(function (event) {
                        renderConversations((event.target && event.target.value) || '');
                    }, 120);
                    elements.searchInput.addEventListener('input', onSearch);
                }

                if (elements.newChatBtn && elements.usersBox) {
                    elements.newChatBtn.addEventListener('click', function () {
                        const isVisible = elements.usersBox.style.display !== 'none';
                        elements.usersBox.style.display = isVisible ? 'none' : 'block';
                    });
                }
            });
        }

        function hidePanel() {
            panel.classList.remove('show');
            panelVisible = false;
            showTyping(false);
            setComposerEnabled(false);
            if (activeSocket) {
                try {
                    activeSocket.close();
                } catch (e) {
                }
                activeSocket = null;
            }
            activeRoomId = null;
            activeConversationId = null;
        }

        function sendCurrentMessage() {
            const text = (input.value || '').trim();
            if (!text || !activeSocket || activeSocket.readyState !== WebSocket.OPEN || !activeRoomId) {
                return;
            }
            activeSocket.send(JSON.stringify({
                message: text,
                cid: Date.now() + '-' + Math.random().toString(36).slice(2, 8)
            }));
            input.value = '';
            showTyping(false);
            typingState = false;

            fetchConversations().then(function () {
                renderConversations((sidebarElements().searchInput || {}).value || '');
            });
        }

        chatBubble.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            if (panelVisible) {
                hidePanel();
            } else {
                showPanel();
            }
        });

        closeBtn.addEventListener('click', function (event) {
            event.preventDefault();
            hidePanel();
        });

        send.addEventListener('click', function () {
            sendCurrentMessage();
        });

        input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendCurrentMessage();
                return;
            }

            if (!activeSocket || activeSocket.readyState !== WebSocket.OPEN || !activeRoomId) {
                return;
            }

            if (!typingState) {
                typingState = true;
                activeSocket.send(JSON.stringify({ action: 'typing', typing: true }));
            }

            clearTimeout(typingTimer);
            typingTimer = setTimeout(function () {
                if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
                    activeSocket.send(JSON.stringify({ action: 'typing', typing: false }));
                }
                typingState = false;
            }, 1000);
        });

        panel.addEventListener('click', function (event) {
            const target = event.target;
            if (target === panel) {
                hidePanel();
            }
        });

        window.openChatInPanel = function (roomId) {
            if (!roomId) return;
            if (!panelVisible) showPanel();
            const normalized = String(roomId).startsWith('conv-') || String(roomId).startsWith('at-') ? String(roomId) : 'conv-' + String(roomId);
            setTimeout(function () {
                const conv = allConversations.find(function (c) {
                    return ('conv-' + c.id) === normalized;
                });
                openRoom(normalized, conv ? conversationTitle(conv) : 'Conversa');
            }, 120);
        };

        window.hautomatizeChatPanel = {
            refreshList: refreshList,
            showPanel: showPanel,
            hidePanel: hidePanel
        };

        setComposerEnabled(false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChatPanel);
    } else {
        initChatPanel();
    }
})();
