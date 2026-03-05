class ChatModule {
    constructor() {
        this.currentConversationId = null;
        this.activeRoomId = null;
        this.activeSocket = null;
        this.typingTimeout = null;
        this.conversations = [];
        this.allUsers = [];
        this.currentUserId = window.userId;
        this.currentUsername = window.username || window.userName || '';
    }

    init() {
        this.showAvailabilityWidget();
        this.loadConversations();
    }

    async loadConversations() {
        try {
            const response = await fetch('/chat/my_conversations/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) throw new Error(`Status ${response.status}`);

            const data = await response.json();
            this.conversations = Array.isArray(data) ? data : (data.conversations || []);

            await this.loadAllUsers();
            this.renderConversations((document.getElementById('chat-search-input') || {}).value || '');
        } catch (error) {
            console.error('Erro ao carregar conversas:', error);
            this.conversations = [];
            this.renderConversations('');
        }
    }

    async loadAllUsers() {
        try {
            const response = await fetch('/api/users/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) throw new Error(`Status ${response.status}`);

            const data = await response.json();
            const users = Array.isArray(data) ? data : (data.users || []);
            this.allUsers = users.filter(user => Number(user.id) !== Number(this.currentUserId));
        } catch (error) {
            console.error('Erro ao carregar funcionários:', error);
            this.allUsers = [];
        }
    }

    renderConversations(filter = '') {
        const list = document.getElementById('chat-list');
        if (!list) return;

        const normalizedFilter = (filter || '').toLowerCase().trim();
        const cards = [];

        this.conversations.forEach(conv => {
            const convName = (conv.title || (conv.participants || []).join(', ') || 'Conversa').trim();
            if (normalizedFilter && !convName.toLowerCase().includes(normalizedFilter)) return;

            cards.push(`
                <div class="chat-item" onclick="chatModule.openExistingConversation(${Number(conv.id)})">
                    <div class="chat-item-avatar">
                        <div class="avatar avatar-xs" style="background:${this.getAvatarColor(convName)}">${this.getInitials(convName)}</div>
                        <div class="chat-item-status online"></div>
                    </div>
                    <div class="chat-item-info">
                        <div class="chat-item-name">${this.escapeHtml(convName)}</div>
                        <div class="chat-item-message">${this.escapeHtml(conv.last_message || 'Nenhuma mensagem')}</div>
                    </div>
                </div>
            `);
        });

        this.allUsers.forEach(user => {
            const userName = (user.name || user.nome || `Usuário ${user.id}`).trim();
            if (normalizedFilter && !userName.toLowerCase().includes(normalizedFilter)) return;

            cards.push(`
                <div class="chat-item" onclick="chatModule.startConversationWithUser(${Number(user.id)}, '${this.escapeForAttr(userName)}')">
                    <div class="chat-item-avatar">
                        <div class="avatar avatar-xs" style="background:${this.getAvatarColor(userName)}">${this.getInitials(userName)}</div>
                        <div class="chat-item-status online"></div>
                    </div>
                    <div class="chat-item-info">
                        <div class="chat-item-name">${this.escapeHtml(userName)}</div>
                        <div class="chat-item-message">Iniciar conversa</div>
                    </div>
                </div>
            `);
        });

        if (!cards.length) {
            list.innerHTML = '<div class="chat-empty">Nenhum funcionário encontrado.</div>';
            return;
        }

        list.innerHTML = cards.join('');
    }

    filterConversations() {
        const input = document.getElementById('chat-search-input');
        this.renderConversations(input ? input.value : '');
    }

    async startConversationWithUser(userId, userName) {
        try {
            const response = await fetch('/chat/create_user_conversation/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ user_id: Number(userId) })
            });
            if (!response.ok) throw new Error(`Status ${response.status}`);

            const data = await response.json();
            if (!data.conversation_id) throw new Error('conversation_id ausente');

            await this.loadConversations();
            await this.openExistingConversation(Number(data.conversation_id), userName);
        } catch (error) {
            console.error('Erro ao criar conversa:', error);
        }
    }

    async openExistingConversation(conversationId, fallbackTitle = '') {
        const conv = this.conversations.find(item => Number(item.id) === Number(conversationId));
        const title = fallbackTitle || (conv ? (conv.title || (conv.participants || []).join(', ')) : '') || 'Conversa';

        this.currentConversationId = Number(conversationId);
        this.activeRoomId = `conv-${this.currentConversationId}`;

        const nameEl = document.getElementById('chat-window-user-name');
        const statusEl = document.getElementById('chat-window-user-status');
        const avatarEl = document.getElementById('chat-window-avatar');

        if (nameEl) nameEl.textContent = title;
        if (statusEl) statusEl.textContent = 'Online';
        if (avatarEl) {
            avatarEl.style.background = this.getAvatarColor(title);
            avatarEl.textContent = this.getInitials(title);
        }

        const panel = document.getElementById('chat-panel');
        const chatWindow = document.getElementById('chat-window');
        if (panel) panel.style.display = 'none';
        if (chatWindow) chatWindow.style.display = 'flex';

        await this.loadMessages(this.activeRoomId);
        this.connectRoomSocket(this.activeRoomId);
        await this.markAsRead(this.currentConversationId);
    }

    async loadMessages(roomId) {
        const messagesEl = document.getElementById('chat-messages');
        if (messagesEl) messagesEl.innerHTML = '<div class="chat-loading">Carregando mensagens...</div>';

        try {
            const response = await fetch(`/api/messages/${encodeURIComponent(roomId)}/`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) throw new Error(`Status ${response.status}`);

            const data = await response.json();
            const messages = Array.isArray(data) ? data : (data.messages || []);
            this.renderMessages(messages);
        } catch (error) {
            console.error('Erro ao carregar mensagens:', error);
            this.renderMessages([]);
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        if (!Array.isArray(messages) || !messages.length) {
            container.innerHTML = '<div class="chat-empty">Nenhuma mensagem ainda.</div>';
            return;
        }

        container.innerHTML = messages.map(msg => {
            const own = Boolean(msg.own) || (msg.user && this.currentUsername && msg.user === this.currentUsername);
            const name = msg.user || 'Usuário';
            const text = msg.message || msg.content || '';
            const time = msg.time || this.formatTime(msg.created || msg.timestamp);
            return `
                <div class="chat-message ${own ? 'sent' : 'received'}">
                    ${!own ? `<div class="avatar avatar-xs" style="background:${this.getAvatarColor(name)}">${this.getInitials(name)}</div>` : ''}
                    <div class="chat-message-content">
                        <div class="chat-message-bubble">
                            <p class="chat-message-text">${this.escapeHtml(text)}</p>
                            <small class="chat-message-time">${this.escapeHtml(time)}</small>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.scrollTop = container.scrollHeight;
    }

    appendMessage(message) {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const own = Boolean(message.own) || (message.user && this.currentUsername && message.user === this.currentUsername);
        const name = message.user || 'Usuário';
        const text = message.message || '';
        const time = message.time || this.formatTime(message.created);

        if (container.querySelector('.chat-empty')) {
            container.innerHTML = '';
        }

        container.insertAdjacentHTML('beforeend', `
            <div class="chat-message ${own ? 'sent' : 'received'}">
                ${!own ? `<div class="avatar avatar-xs" style="background:${this.getAvatarColor(name)}">${this.getInitials(name)}</div>` : ''}
                <div class="chat-message-content">
                    <div class="chat-message-bubble">
                        <p class="chat-message-text">${this.escapeHtml(text)}</p>
                        <small class="chat-message-time">${this.escapeHtml(time)}</small>
                    </div>
                </div>
            </div>
        `);

        container.scrollTop = container.scrollHeight;
    }

    connectRoomSocket(roomId) {
        if (this.activeSocket) {
            try { this.activeSocket.close(); } catch (_) {}
            this.activeSocket = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/ws/chat/${roomId}/`;

        try {
            this.activeSocket = new WebSocket(wsUrl);
        } catch (error) {
            console.error('Erro ao abrir WebSocket:', error);
            return;
        }

        this.activeSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data || '{}');

                if (data.type === 'typing') {
                    const sameUser = this.currentUsername && data.user && data.user === this.currentUsername;
                    if (!sameUser) this.showTypingIndicator(Boolean(data.typing), data.user || 'Alguém');
                    return;
                }

                if (data.type === 'message' || data.type === 'chat_message' || data.message) {
                    this.appendMessage({
                        user: data.user,
                        message: data.message,
                        created: data.created,
                        time: this.formatTime(data.created),
                        own: Boolean(this.currentUsername && data.user === this.currentUsername)
                    });
                    this.loadConversations();
                }
            } catch (_) {}
        };
    }

    sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input) return;

        const text = (input.value || '').trim();
        if (!text || !this.activeSocket || this.activeSocket.readyState !== WebSocket.OPEN || !this.activeRoomId) return;

        this.activeSocket.send(JSON.stringify({
            message: text,
            cid: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        }));

        input.value = '';
        input.style.height = 'auto';
        this.showTypingIndicator(false);
    }

    handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    handleTyping() {
        const input = document.getElementById('chat-input');
        if (input) {
            input.style.height = 'auto';
            input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
        }

        if (!this.activeSocket || this.activeSocket.readyState !== WebSocket.OPEN) return;

        this.activeSocket.send(JSON.stringify({ typing: true }));
        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            if (this.activeSocket && this.activeSocket.readyState === WebSocket.OPEN) {
                this.activeSocket.send(JSON.stringify({ typing: false }));
            }
        }, 1200);
    }

    showTypingIndicator(isTyping, username = 'Alguém') {
        const indicator = document.getElementById('chat-typing-indicator');
        if (!indicator) return;
        if (!isTyping) {
            indicator.style.display = 'none';
            return;
        }

        indicator.style.display = 'flex';
        indicator.lastChild.textContent = `${username} digitando...`;

        setTimeout(() => {
            indicator.style.display = 'none';
        }, 2200);
    }

    attachChatFile() {
        const input = document.getElementById('chat-file-input');
        if (input) input.click();
    }

    handleChatFileSelected(event) {
        const file = event && event.target && event.target.files ? event.target.files[0] : null;
        if (!file) return;
        console.log('Arquivo selecionado (upload não implementado):', file.name);
    }

    togglePanel() {
        const panel = document.getElementById('chat-panel');
        const chatWindow = document.getElementById('chat-window');
        if (!panel) return;

        panel.style.display = 'block';
        if (chatWindow) chatWindow.style.display = 'none';
        this.loadConversations();
    }

    closePanel() {
        const panel = document.getElementById('chat-panel');
        if (panel) panel.style.display = 'none';
    }

    closeChatWindow() {
        const panel = document.getElementById('chat-panel');
        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) chatWindow.style.display = 'none';
        if (panel) panel.style.display = 'block';

        this.currentConversationId = null;
        this.activeRoomId = null;

        if (this.activeSocket) {
            try { this.activeSocket.close(); } catch (_) {}
            this.activeSocket = null;
        }
    }

    switchTab(tab) {
        document.querySelectorAll('.chat-tab').forEach(button => {
            button.classList.toggle('active', button.getAttribute('data-tab') === tab);
        });

        document.querySelectorAll('.chat-tab-content').forEach(content => {
            content.style.display = 'none';
        });

        const tabEl = document.getElementById(`${tab}-tab`);
        if (tabEl) tabEl.style.display = 'block';

        if (tab === 'conversations') {
            this.loadConversations();
        } else if (tab === 'notifications') {
            this.renderNotifications([]);
        }
    }

    renderNotifications(notifications) {
        const list = document.getElementById('notifications-list');
        if (!list) return;

        if (!notifications || !notifications.length) {
            list.innerHTML = '<div class="chat-empty">Nenhuma notificação</div>';
            return;
        }

        list.innerHTML = notifications.map(item => `
            <div class="notification-item ${item.read ? '' : 'unread'}">
                <div class="notification-title">${this.escapeHtml(item.title || 'Notificação')}</div>
                <div class="notification-content">${this.escapeHtml(item.content || '')}</div>
                <div class="notification-time">${this.escapeHtml(this.formatTime(item.created_at))}</div>
            </div>
        `).join('');
    }

    markAllNotificationsRead() {
        this.renderNotifications([]);
    }

    async markAsRead(conversationId) {
        try {
            await fetch('/chat/mark_read/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ conversation_id: Number(conversationId) })
            });
        } catch (error) {
            console.error('Erro ao marcar conversa como lida:', error);
        }
    }

    toggleAvailability(checked) {
        const statusIndicator = document.getElementById('status-indicator');
        const text = document.getElementById('availability-text');
        if (statusIndicator) statusIndicator.style.background = checked ? '#4caf50' : '#ff9800';
        if (text) text.textContent = checked ? 'Disponível' : 'Indisponível';
    }

    updateUserStatus() {}

    showAvailabilityWidget() {
        const widget = document.getElementById('availability-widget');
        if (widget) widget.style.display = 'block';
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '';

        const now = new Date();
        const diffMs = now - date;
        const diffMin = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMin / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMin < 1) return 'Agora';
        if (diffMin < 60) return `${diffMin}m`;
        if (diffHours < 24) return `${diffHours}h`;
        if (diffDays < 7) return `${diffDays}d`;

        return date.toLocaleDateString('pt-BR');
    }

    getInitials(name) {
        if (!name) return '?';
        return String(name)
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map(part => part[0] || '')
            .join('')
            .toUpperCase() || '?';
    }

    getAvatarColor(seed) {
        const colors = ['#16a34a', '#0ea5e9', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4'];
        const text = String(seed || 'user');
        let hash = 0;
        for (let i = 0; i < text.length; i += 1) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash |= 0;
        }
        return colors[Math.abs(hash) % colors.length];
    }

    getCsrfToken() {
        const byInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (byInput && byInput.value) return byInput.value;

        const pair = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return pair ? pair.split('=')[1] : '';
    }

    escapeHtml(text) {
        const value = String(text == null ? '' : text);
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    escapeForAttr(text) {
        return this.escapeHtml(text).replace(/'/g, '\\&#039;');
    }
}

(function initChatModule() {
    const start = () => {
        window.chatModule = new ChatModule();
        window.chatModule.init();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
