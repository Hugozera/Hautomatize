class ChatManager {
    constructor() {
        this.ws = null;
        this.currentId = null;
        this.currentType = null;
        this.attachments = [];
        this.pendingMessages = [];
        this.groupSelection = new Map();
        this.pc = null;
        this.localStream = null;
        this.remoteStream = null;
        this.init();
    }

    init() {
        this.elements = {
            list: document.querySelectorAll('.conversation-item'),
            area: document.getElementById('conv-area'),
            title: document.getElementById('conv-title'),
            subtitle: document.getElementById('conv-subtitle'),
            input: document.getElementById('conv-input'),
            send: document.getElementById('conv-send'),
            form: document.getElementById('message-form'),
            attachBtn: document.getElementById('attach-btn'),
            fileInput: document.getElementById('file-input'),
            attachmentPreview: document.getElementById('attachment-preview'),
            emojiBtn: document.getElementById('emoji-btn'),
            emojiPicker: document.getElementById('emoji-picker'),
            toggleInfo: document.getElementById('toggle-info'),
            infoPanel: document.getElementById('info-panel'),
            closeInfo: document.getElementById('close-info'),
            infoContent: document.getElementById('info-content')
        };

        this.bindEvents();
        this.loadEmojis();
    }

    bindEvents() {
        // Clique nas conversas (delegation: suporta itens dinâmicos)
        const convContainer = document.querySelector('.ig-conversations');
        if (convContainer) {
            convContainer.addEventListener('click', (e) => {
                const item = e.target.closest('.ig-conversation-item');
                if (item) {
                    e.preventDefault();
                    this.openConversation(item);
                }
            });
        }

        // Envio de mensagem
        this.elements.form.addEventListener('submit', (e) => this.sendMessage(e));

        // Anexos
        this.elements.attachBtn.addEventListener('click', () => this.elements.fileInput.click());
        this.elements.fileInput.addEventListener('change', (e) => this.handleFiles(e.target.files));

        // Emoji
        this.elements.emojiBtn.addEventListener('click', () => this.toggleEmojiPicker());

        // Info panel
        this.elements.toggleInfo.addEventListener('click', () => this.toggleInfoPanel());
        this.elements.closeInfo.addEventListener('click', () => this.hideInfoPanel());

        // Busca
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('input', () => this.search(searchInput.value));

        // enable/disable send button based on input content
        if (this.elements.input && this.elements.send) {
            const updateSendState = () => {
                const hasText = (this.elements.input.value || '').trim().length > 0;
                const hasAttach = this.attachments && this.attachments.length > 0;
                this.elements.send.disabled = !(hasText || hasAttach);
            };
            this.elements.input.addEventListener('input', (ev) => { updateSendState(); this.handleTyping(); });
            // initial
            updateSendState();
        }

        // typing debounce
        this._typingTimer = null;

        // Modal nova conversa
        const newChatBtn = document.getElementById('new-chat-btn');
        const newChatModal = document.getElementById('new-chat-modal');
        const closeModal = document.getElementById('close-modal');
        const modalSearch = document.getElementById('modal-search');
        const suggestionsList = document.getElementById('suggestions-list');
        const createGroupBtn = document.getElementById('create-group-btn');
        const newGroupBtn = document.getElementById('new-group-btn');
        const videoBtn = document.getElementById('chat-video-btn');
        const audioBtn = document.getElementById('chat-audio-btn');
        const quickVideoBtn = document.getElementById('quick-video-btn');
        const endCallBtn = document.getElementById('end-call-btn');
        const closeCallModalBtn = document.getElementById('close-call-modal');
        const muteCallBtn = document.getElementById('mute-call-btn');

        if (newChatBtn && newChatModal) {
            newChatBtn.addEventListener('click', () => { newChatModal.style.display = 'block'; if(modalSearch) modalSearch.focus(); });
        }
        if (newGroupBtn && newChatModal) {
            newGroupBtn.addEventListener('click', () => { newChatModal.style.display = 'block'; if(modalSearch) modalSearch.focus(); });
        }
        if (closeModal && newChatModal) {
            closeModal.addEventListener('click', () => { newChatModal.style.display = 'none'; if(suggestionsList) suggestionsList.innerHTML = ''; if(modalSearch) modalSearch.value = ''; this.groupSelection.clear(); });
        }

        if (modalSearch) {
            let searchTimer = null;
            modalSearch.addEventListener('input', (e) => {
                const q = (e.target.value || '').trim();
                suggestionsList.innerHTML = '';
                if (searchTimer) clearTimeout(searchTimer);
                if (!q) return;
                // debounce
                searchTimer = setTimeout(() => {
                    // buscar pessoas do sistema
                    fetch(`/api/users/?q=${encodeURIComponent(q)}`)
                        .then(r => r.json())
                        .then(js => {
                            const users = js.users || [];
                            users.slice(0,8).forEach(u => {
                                const div = document.createElement('div');
                                div.className = 'ig-suggestion-item';
                                div.dataset.id = u.id;
                                div.dataset.nome = u.name;
                                div.dataset.userId = u.id;
                                div.innerHTML = `<div class="ig-suggestion-avatar"><div class="ig-avatar-placeholder small">${(u.name||'')[0]||''}</div></div><div class="ig-suggestion-info"><span class="ig-suggestion-name">${u.name}</span><span class="ig-suggestion-detail">Usuário</span></div><input type="checkbox" class="ig-suggestion-check" />`;
                                div.addEventListener('click', (ev) => { ev.preventDefault(); this.createConversationWithUser(u.id, u.name); newChatModal.style.display = 'none'; });
                                div.querySelector('.ig-suggestion-check').addEventListener('click', (ev) => {
                                    ev.stopPropagation();
                                    if (ev.target.checked) this.groupSelection.set(String(u.id), u.name);
                                    else this.groupSelection.delete(String(u.id));
                                });
                                suggestionsList.appendChild(div);
                            });
                        }).catch(() => {});

                    // buscar empresas
                    fetch(`/empresas/api/search/?q=${encodeURIComponent(q)}`)
                        .then(r => r.json())
                        .then(js => {
                            const results = js.results || js || [];
                            results.slice(0,8).forEach(e => {
                                const div = document.createElement('div');
                                div.className = 'ig-suggestion-item';
                                div.dataset.id = e.id;
                                div.dataset.nome = e.nome || e.nome_fantasia || '';
                                div.innerHTML = `<div class="ig-suggestion-avatar"><div class="ig-avatar-placeholder small"><i class="bi bi-building"></i></div></div><div class="ig-suggestion-info"><span class="ig-suggestion-name">${div.dataset.nome}</span><span class="ig-suggestion-detail">Empresa</span></div>`;
                                div.addEventListener('click', (ev) => { ev.preventDefault(); this.createConversationWithEmpresa(e.id, div.dataset.nome); newChatModal.style.display = 'none'; });
                                suggestionsList.appendChild(div);
                            });
                        }).catch(() => {});
                    // buscar pessoas direto na tabela Pessoa (funcionários)
                    fetch(`/api/pessoas/?q=${encodeURIComponent(q)}`)
                        .then(r => r.json())
                        .then(js => {
                            const results = js.results || [];
                            results.slice(0,8).forEach(p => {
                                const div = document.createElement('div');
                                div.className = 'ig-suggestion-item';
                                div.dataset.id = 'pessoa-' + p.id;
                                div.dataset.nome = p.nome || '';
                                const uid = p.usuario_id || p.id;
                                div.dataset.userId = uid;
                                div.innerHTML = `<div class="ig-suggestion-avatar"><div class="ig-avatar-placeholder small">${(p.nome||'')[0]||''}</div></div><div class="ig-suggestion-info"><span class="ig-suggestion-name">${p.nome}</span><span class="ig-suggestion-detail">Funcionário</span></div><input type="checkbox" class="ig-suggestion-check" />`;
                                div.addEventListener('click', (ev) => { ev.preventDefault(); this.createConversationWithUser(p.usuario_id || p.id, p.nome); newChatModal.style.display = 'none'; });
                                div.querySelector('.ig-suggestion-check').addEventListener('click', (ev) => {
                                    ev.stopPropagation();
                                    if (ev.target.checked) this.groupSelection.set(String(uid), p.nome);
                                    else this.groupSelection.delete(String(uid));
                                });
                                suggestionsList.appendChild(div);
                            });
                        }).catch(() => {});
                }, 250);
            });
        }

        if (createGroupBtn) {
            createGroupBtn.addEventListener('click', () => {
                const ids = Array.from(this.groupSelection.keys()).map(Number).filter(Boolean);
                if (ids.length < 2) {
                    alert('Selecione ao menos 2 participantes para criar grupo.');
                    return;
                }
                const title = prompt('Nome do grupo:') || 'Grupo';
                this.createGroupConversation(title, ids);
                if (newChatModal) newChatModal.style.display = 'none';
            });
        }

        if (videoBtn) videoBtn.addEventListener('click', () => this.startCall('video'));
        if (audioBtn) audioBtn.addEventListener('click', () => this.startCall('audio'));
        if (quickVideoBtn) quickVideoBtn.addEventListener('click', () => this.startCall('video'));
        if (endCallBtn) endCallBtn.addEventListener('click', () => this.endCall());
        if (closeCallModalBtn) closeCallModalBtn.addEventListener('click', () => this.endCall());
        if (muteCallBtn) muteCallBtn.addEventListener('click', () => this.toggleMute());

        // Tabs switching (Todas / Empresas / Pessoas)
        document.querySelectorAll('.ig-tab').forEach(tab => {
            tab.addEventListener('click', (ev) => {
                ev.preventDefault();
                document.querySelectorAll('.ig-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const which = tab.dataset.tab;
                document.querySelectorAll('.ig-conversation-group').forEach(g => g.classList.remove('active'));
                const target = document.getElementById('conv-' + which);
                if (target) target.classList.add('active');
            });
        });

        // 'Enviar mensagem' button in empty state opens new chat modal
        const startNewChatBtn = document.getElementById('start-new-chat');
        if (startNewChatBtn) startNewChatBtn.addEventListener('click', () => { const m = document.getElementById('new-chat-modal'); if (m) { m.style.display = 'block'; const s = document.getElementById('modal-search'); if (s) s.focus(); } });
    }

    handleTyping() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        // send typing true immediately
        this.sendTyping(true);
        if (this._typingTimer) clearTimeout(this._typingTimer);
        this._typingTimer = setTimeout(() => { this.sendTyping(false); }, 1500);
    }

    sendTyping(state) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        try {
            this.ws.send(JSON.stringify({ action: 'typing', typing: !!state }));
        } catch (e) {
            // ignore
        }
    }

    openConversation(item) {
        // Remove active class de todos
        document.querySelectorAll('.conversation-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        const rawId = item.dataset.id;
        const type = item.dataset.type;
        const name = (item.querySelector('.ig-conversation-name') || item.querySelector('.conversation-name') || { textContent: '' }).textContent || '';

        // Open existing conversations directly (recent list uses conv-<id>)
        if (typeof rawId === 'string' && rawId.startsWith('conv-')) {
            this.currentId = rawId;
            this.currentType = 'conversa';
            this.elements.title.textContent = `Conversa - ${name}`;

            const inputArea = document.getElementById('input-area');
            if (inputArea) inputArea.style.display = '';
            if (this.elements.form) this.elements.form.style.display = '';
            if (this.elements.input) this.elements.input.focus();

            this.connectWebSocket(this.currentId);
            this.clearMessages();
            this.loadMessageHistory(this.currentId);
            this.markConversationRead(this.currentId);
            this.renderConversationInfo();
            return;
        }

        // Plain pessoa entry (data-id pessoa-<id>) should create/open a direct conversation by user id
        if (typeof rawId === 'string' && rawId.startsWith('pessoa-')) {
            const userId = item.dataset.userId || String(rawId).replace(/^pessoa-/, '');
            this.createConversationWithUser(userId, name || item.dataset.nome || 'Conversa');
            return;
        }

        // If this is an atendimento entry (at-<id>) keep existing behavior
        const id = rawId;

        this.currentId = id;
        this.currentType = type;
        this.elements.title.textContent = `Conversa - ${name}`;

        if (type === 'pessoa') {
            this.loadUserInfo(id);
        }

        // show input area and form
        const inputArea = document.getElementById('input-area');
        if (inputArea) inputArea.style.display = '';
        if (this.elements.form) this.elements.form.style.display = '';
        if (this.elements.input) this.elements.input.focus();

        this.connectWebSocket(id);
        this.clearMessages();
        this.loadMessageHistory(id);
        // marcar como lida ao abrir
        this.markConversationRead(id);
        this.renderConversationInfo();
    }

    connectWebSocket(id) {
        if (this.ws) {
            this.ws.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsPath = id.startsWith('at-') ? 
            `/ws/atendimento/${id.substring(3)}/` : 
            `/ws/chat/${id}/`;

        this.ws = new WebSocket(protocol + window.location.host + wsPath);

        this.ws.onmessage = (e) => this.receiveMessage(e);
        this.ws.onopen = () => {
            console.log('Conectado ao chat');
            // enable send UI when socket opens (if input has content it'll be enabled by input listener)
            if (this.elements && this.elements.send) {
                const ev = new Event('input');
                if (this.elements.input) this.elements.input.dispatchEvent(ev);
            }
            // flush any pending messages queued while socket was connecting
            if (this.pendingMessages && this.pendingMessages.length > 0) {
                this.pendingMessages.forEach(msg => {
                    try { this.ws.send(JSON.stringify(msg)); } catch (e) { console.error('Erro enviando pending message', e); }
                });
                this.pendingMessages = [];
            }
        };
        this.ws.onclose = () => console.log('Desconectado do chat');
    }

    async sendMessage(e) {
        e.preventDefault();
        
        const text = this.elements.input.value.trim();
        
        if (!text && this.attachments.length === 0) return;
        // Prepare payload
        const cid = 'c' + Date.now() + '-' + Math.random().toString(36).slice(2,8);
        const payload = { type: 'message', message: text, cid: cid };

        // If there are attachments, upload first and include resulting files in payload
        if (this.attachments.length > 0) {
            try {
                const files = await this.uploadAttachments();
                payload.attachments = files || [];
            } catch (err) {
                console.error('Erro no upload de anexos:', err);
            }
        }

        // optimistic UI: display immediately as own (mark pending with cid)
        this.displayMessage({ user: (window.userName || 'Você'), message: payload.message, time: new Date().toLocaleTimeString(), own: true, attachments: payload.attachments || [], cid: cid });
        this.elements.area.scrollTop = this.elements.area.scrollHeight;

        // bump this conversation to top of recent list
        try { this.bumpConversation(this.currentId || payload.conversation_id || payload.cid); } catch (e) {}

        // If websocket not ready, queue the message to be sent when it opens
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.pendingMessages.push(payload);
        } else {
            this.ws.send(JSON.stringify(payload));
        }

        this.elements.input.value = '';
        this.clearAttachments();
    }

    receiveMessage(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'call') {
                this.handleCallSignal(data);
                return;
            }
            if (data.type === 'typing') {
                const el = document.getElementById('typing-indicator');
                if (el) {
                    if (data.typing) {
                        el.textContent = `${data.user} está digitando...`;
                        el.style.display = '';
                    } else {
                        el.style.display = 'none';
                        el.textContent = '';
                    }
                }
                return;
            }

            if (data.type === 'message' || (!data.type && data.message)) {
                // If server echoed a cid, try to find existing optimistic message and upgrade it
                if (data.cid) {
                    const existing = this.elements.area.querySelector(`[data-cid="${data.cid}"]`);
                    if (existing) {
                        // update content and remove pending state
                        const sender = existing.querySelector('.message-sender');
                        const timeEl = existing.querySelector('.message-time');
                        const contentEl = existing.querySelector('.message-content');
                        if (sender) sender.textContent = data.user || 'Anônimo';
                        if (timeEl) timeEl.textContent = new Date(data.created || Date.now()).toLocaleTimeString();
                        // replace message text
                        if (contentEl) {
                            contentEl.innerHTML = '';
                            const p = document.createElement('p'); p.textContent = data.message || '';
                            contentEl.appendChild(p);
                        }
                        existing.classList.remove('pending');
                        return;
                    }
                }

                this.displayMessage({
                    user: data.user || 'Anônimo',
                    message: data.message || '',
                    time: new Date().toLocaleTimeString(),
                    own: (data.user === (window.userName || window.USERNAME || '')),
                    attachments: data.attachments || [],
                    created: data.created,
                    cid: data.cid
                });
                // bump conversation in recent list if conversation_id provided
                try { if (data.conversation_id) this.bumpConversation('conv-' + String(data.conversation_id)); } catch (e) {}
                // hide typing indicator when a message arrives
                const el = document.getElementById('typing-indicator'); if (el) { el.style.display = 'none'; el.textContent = ''; }
            }
        } catch (err) {
            console.error('Erro ao processar mensagem:', err);
        }
    }

    displayMessage(msg) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${msg.own ? 'own' : ''}`;
        if (msg.cid) wrapper.dataset.cid = msg.cid;
        if (msg.own && !msg.created) wrapper.classList.add('pending');

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        // Header
        const header = document.createElement('div');
        header.className = 'message-header';
        header.innerHTML = `
            <span class="message-sender">${msg.user}</span>
            <span class="message-time">${msg.time}</span>
        `;

        // Conteúdo
        const content = document.createElement('div');
        content.className = 'message-content';
        
        if (msg.message) {
            const p = document.createElement('p');
            p.textContent = msg.message;
            content.appendChild(p);
        }

        // Anexos
        if (msg.attachments && msg.attachments.length > 0) {
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.className = 'message-attachments';
            
            msg.attachments.forEach(att => {
                if (att.type.startsWith('image/')) {
                    const thumb = document.createElement('div');
                    thumb.className = 'attachment-thumb';
                    thumb.innerHTML = `<img src="${att.url}" alt="${att.name}" onclick="window.open('${att.url}')">`;
                    attachmentsDiv.appendChild(thumb);
                } else {
                    const fileDiv = document.createElement('div');
                    fileDiv.className = 'attachment-file';
                    fileDiv.innerHTML = `
                        <i class="bi bi-file-earmark"></i>
                        <div class="file-info">
                            <div class="file-name">${att.name}</div>
                            <div class="file-size">${this.formatFileSize(att.size)}</div>
                        </div>
                        <a href="${att.url}" download="${att.name}" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-download"></i>
                        </a>
                    `;
                    attachmentsDiv.appendChild(fileDiv);
                }
            });
            
            content.appendChild(attachmentsDiv);
        }

        bubble.appendChild(header);
        bubble.appendChild(content);
        wrapper.appendChild(bubble);

        this.elements.area.appendChild(wrapper);
        this.elements.area.scrollTop = this.elements.area.scrollHeight;
    }

    handleFiles(files) {
        for (let file of files) {
            // Validações
            if (file.size > 10 * 1024 * 1024) { // 10MB
                alert('Arquivo muito grande. Máximo 10MB');
                continue;
            }

            this.attachments.push(file);
            this.previewFile(file);
        }
    }

    previewFile(file) {
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const preview = document.createElement('div');
            preview.className = 'preview-item';
            
            if (file.type.startsWith('image/')) {
                preview.innerHTML = `
                    <img src="${e.target.result}" alt="${file.name}">
                    <button class="remove-file" data-filename="${file.name}">
                        <i class="bi bi-x"></i>
                    </button>
                `;
            } else {
                preview.innerHTML = `
                    <div class="file-preview">
                        <i class="bi bi-file-earmark"></i>
                        <span class="file-name">${file.name}</span>
                    </div>
                    <button class="remove-file" data-filename="${file.name}">
                        <i class="bi bi-x"></i>
                    </button>
                `;
            }

            preview.querySelector('.remove-file').addEventListener('click', () => {
                this.removeAttachment(file.name);
                preview.remove();
            });

            this.elements.attachmentPreview.appendChild(preview);
        };

        if (file.type.startsWith('image/')) {
            reader.readAsDataURL(file);
        } else {
            reader.readAsText(file);
        }
    }

    async uploadAttachments() {
        const formData = new FormData();
        this.attachments.forEach(file => formData.append('files', file));
        formData.append('conversation_id', this.currentId);

        try {
            const response = await fetch('/api/upload-attachments/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: formData
            });

            const data = await response.json();
            // return uploaded files info for inclusion in message payload
            return data.files || [];

        } catch (error) {
            console.error('Erro ao fazer upload:', error);
            alert('Erro ao enviar arquivos');
            return [];
        }
    }

    removeAttachment(filename) {
        this.attachments = this.attachments.filter(f => f.name !== filename);
    }

    clearAttachments() {
        this.attachments = [];
        this.elements.attachmentPreview.innerHTML = '';
        this.elements.fileInput.value = '';
    }

    bumpConversation(id) {
        if (!id) return;
        const raw = String(id);
        // normalize to possible selectors
        const candidates = [raw, `conv-${raw}`, raw.replace(/^conv-/, ''), raw.replace(/^pessoa-/, ''), `pessoa-${raw.replace(/^pessoa-/, '')}`];
        let item = null;
        for (let c of candidates) {
            const sel = `[data-id="${c}"]`;
            item = document.querySelector(sel);
            if (item) break;
        }
        if (!item) return;
        // move to top of first conversation group
        const container = document.querySelector('.ig-conversations');
        if (!container) return;
        const firstGroup = container.querySelector('.ig-conversation-group');
        if (!firstGroup) return;
        try {
            firstGroup.insertBefore(item, firstGroup.firstChild);
        } catch (e) {
            // fallback: prepend to container
            try { container.insertBefore(item, container.firstChild); } catch (ee) {}
        }
    }

    search(query) {
        const q = (query || '').trim().toLowerCase();
        const items = document.querySelectorAll('.ig-conversation-item');
        if (!q) {
            items.forEach(i => i.style.display = 'flex');
            // show groups if any
            document.querySelectorAll('.ig-conversation-group').forEach(g => g.classList.add('active'));
            return;
        }

        items.forEach(i => {
            try {
                const nameEl = i.querySelector('.ig-conversation-name');
                const previewEl = i.querySelector('.ig-preview-text') || i.querySelector('.ig-conversation-preview');
                const name = nameEl ? (nameEl.textContent || '') : '';
                const preview = previewEl ? (previewEl.textContent || '') : '';
                const dataId = i.dataset.id || '';
                const hay = (name + ' ' + preview + ' ' + dataId).toLowerCase();
                if (hay.indexOf(q) !== -1) {
                    i.style.display = 'flex';
                } else {
                    i.style.display = 'none';
                }
            } catch (err) {
                i.style.display = 'none';
            }
        });
        // hide empty groups
        document.querySelectorAll('.ig-conversation-group').forEach(g => {
            const visible = Array.from(g.querySelectorAll('.ig-conversation-item')).some(el => el.style.display !== 'none');
            if (visible) g.classList.add('active'); else g.classList.remove('active');
        });
    }

    toggleEmojiPicker() {
        if (this.elements.emojiPicker.style.display === 'none') {
            this.elements.emojiPicker.style.display = 'block';
        } else {
            this.elements.emojiPicker.style.display = 'none';
        }
    }

    loadEmojis() {
        // Carregar emojis comuns
        const emojis = ['😊', '😂', '❤️', '👍', '😢', '😡', '🎉', '🔥'];
        this.elements.emojiPicker.innerHTML = emojis.map(e => 
            `<span class="emoji" onclick="chatManager.insertEmoji('${e}')">${e}</span>`
        ).join('');
    }

    insertEmoji(emoji) {
        this.elements.input.value += emoji;
        this.elements.emojiPicker.style.display = 'none';
    }

    toggleInfoPanel() {
        if (this.elements.infoPanel.classList.contains('show')) {
            this.hideInfoPanel();
        } else {
            this.showInfoPanel();
        }
    }

    showInfoPanel() {
        this.elements.infoPanel.classList.add('show');
    }

    hideInfoPanel() {
        this.elements.infoPanel.classList.remove('show');
    }

    loadUserInfo(id) {
        const userId = id.replace('pessoa-', '');
        
        fetch(`/api/user/${userId}/info/`)
            .then(r => r.json())
            .then(data => {
                this.elements.infoContent.innerHTML = `
                    <div class="user-info">
                        <div class="user-avatar-large">
                            ${data.foto ? `<img src="${data.foto}" alt="${data.nome}">` : 
                                `<div class="avatar-placeholder">${data.nome[0]}</div>`}
                        </div>
                        <h5>${data.nome}</h5>
                        <p class="text-muted">${data.cargo || 'Funcionário'}</p>
                        
                        <div class="info-section">
                            <h6>Contato</h6>
                            <p><i class="bi bi-envelope"></i> ${data.email}</p>
                            ${data.telefone ? `<p><i class="bi bi-telephone"></i> ${data.telefone}</p>` : ''}
                        </div>
                        
                        <div class="info-section">
                            <h6>Departamento</h6>
                            <p>${data.departamento || '—'}</p>
                        </div>
                    </div>
                `;
            });
    }

    loadMessageHistory(id) {
        // Carregar histórico completo via API para garantir persistência ao recarregar.
        fetch(`/api/messages/${id}/`)
            .then(r => {
                if (!r.ok) throw new Error('history_fetch_failed');
                return r.json();
            })
            .then(messages => {
                this.clearMessages();
                (messages || []).forEach(msg => {
                    this.displayMessage({
                        user: msg.user || 'Anônimo',
                        message: msg.message || '',
                        time: msg.time || new Date(msg.created || Date.now()).toLocaleTimeString(),
                        own: !!msg.own,
                        attachments: msg.attachments || [],
                        created: msg.created,
                    });
                });
                this.elements.area.scrollTop = this.elements.area.scrollHeight;
            })
            .catch(() => {
                // fallback: leave empty, websocket may still stream recent messages
                this.clearMessages();
            });
    }

    clearMessages() {
        this.elements.area.innerHTML = '';
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    getCookie(name) {
        const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return v ? v[2] : null;
    }

    markConversationRead(id) {
        if (!id) return;
        // mark_read endpoint only supports Conversation IDs (conv-<id>)
        if (!(typeof id === 'string' && id.startsWith('conv-'))) return;
        // espera id no formato 'conv-<num>' ou número
        const convId = (typeof id === 'string' && id.startsWith('conv-')) ? id.split('-')[1] : id;
        if (!convId) return;

        // pega badge local e o valor para decrementar o bubble
        // try several possible data-id formats inserted by templates
        const convEl = document.querySelector(`[data-id="conv-${convId}"], [data-id="${convId}"], [data-id="pessoa-${convId}"], [data-id="at-${convId}"]`);
        let localCount = 0;
        if (convEl) {
            const badge = convEl.querySelector('.local-unread');
            if (badge) {
                localCount = parseInt(badge.textContent || '0') || 0;
                badge.remove();
            }
        }

        // chamada ao endpoint para persistir last_read
        fetch('/chat/mark_read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ conversation_id: convId })
        }).then(r => r.json()).then(js => {
            // atualizar badge global decrementando pelo localCount
            if (localCount > 0) {
                const bubbleBadge = document.querySelector('#chatBubble .chat-badge');
                if (bubbleBadge) {
                    let n = parseInt(bubbleBadge.textContent || '0') || 0;
                    n = Math.max(0, n - localCount);
                    if (n <= 0) {
                        bubbleBadge.style.display = 'none';
                        bubbleBadge.textContent = '0';
                    } else {
                        bubbleBadge.textContent = n;
                    }
                }
            }
        }).catch(() => {});
    }

    createConversationWithUser(userId, name) {
        if (!userId || Number.isNaN(Number(userId))) {
            console.error('userId inválido para criar conversa:', userId);
            return;
        }
        fetch('/chat/create_user_conversation/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_id: userId })
        }).then(r => r.json()).then(js => {
            if (js.conversation_id) {
                const convId = js.conversation_id;
                this.currentId = `conv-${convId}`;
                this.currentType = 'conversa';
                this.elements.title.textContent = name || 'Conversa';
                this.connectWebSocket(this.currentId);
                this.clearMessages();
                this.loadMessageHistory(this.currentId);
                    // marcar como lida na criação/abertura
                    this.markConversationRead(this.currentId);
                this.renderConversationInfo();
                if (this.elements.input) this.elements.input.focus();
                if (this.elements.form) this.elements.form.style.display = '';
            }
        }).catch(err => { console.error('Erro criando conversa:', err); });
    }

    createConversationWithEmpresa(empresaId, nome) {
        fetch('/chat/create_empresa_conversation/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ empresa_id: empresaId })
        }).then(r => r.json()).then(js => {
            if (js.conversation_id) {
                const convId = js.conversation_id;
                this.currentId = `conv-${convId}`;
                this.currentType = 'conversa';
                this.elements.title.textContent = nome || 'Empresa';
                this.connectWebSocket(this.currentId);
                this.clearMessages();
                this.loadMessageHistory(this.currentId);
                    // marcar como lida na criação/abertura
                    this.markConversationRead(this.currentId);
                this.renderConversationInfo();
                if (this.elements.input) this.elements.input.focus();
                if (this.elements.form) this.elements.form.style.display = '';
            }
        }).catch(err => { console.error('Erro criando conversa:', err); });
    }

    createGroupConversation(title, userIds) {
        fetch('/chat/create_group_conversation/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title, user_ids: userIds })
        }).then(r => r.json()).then(js => {
            if (js.conversation_id) {
                this.groupSelection.clear();
                this.currentId = `conv-${js.conversation_id}`;
                this.currentType = 'conversa';
                this.elements.title.textContent = title || 'Grupo';
                this.connectWebSocket(this.currentId);
                this.clearMessages();
                this.loadMessageHistory(this.currentId);
                this.markConversationRead(this.currentId);
                this.renderConversationInfo();
            }
        }).catch(err => console.error('Erro criando grupo:', err));
    }

    renderConversationInfo() {
        if (!this.elements.infoContent || !this.currentId) return;
        const room = this.currentId;
        this.elements.infoContent.innerHTML = `
            <div class="info-tabs">
                <button class="info-tab active" data-tab="about">Detalhes</button>
                <button class="info-tab" data-tab="media">Mídias</button>
            </div>
            <div class="info-tab-content" id="info-about">
                <p><strong>Sala:</strong> ${room}</p>
                <p class="text-muted">Conversa segura Hautomatize</p>
            </div>
            <div class="info-tab-content" id="info-media" style="display:none;"></div>
        `;

        const tabs = this.elements.infoContent.querySelectorAll('.info-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const which = tab.dataset.tab;
                const about = document.getElementById('info-about');
                const media = document.getElementById('info-media');
                if (which === 'media') {
                    if (about) about.style.display = 'none';
                    if (media) media.style.display = '';
                    this.loadMediaTab(room);
                } else {
                    if (about) about.style.display = '';
                    if (media) media.style.display = 'none';
                }
            });
        });
    }

    loadMediaTab(room) {
        const mediaBox = document.getElementById('info-media');
        if (!mediaBox) return;
        mediaBox.innerHTML = '<p class="text-muted">Carregando mídias...</p>';
        fetch(`/api/messages/${room}/`).then(r => r.json()).then(list => {
            const all = [];
            (list || []).forEach(m => (m.attachments || []).forEach(a => all.push(a)));
            if (!all.length) {
                mediaBox.innerHTML = '<p class="text-muted">Nenhuma mídia compartilhada.</p>';
                return;
            }
            const grid = document.createElement('div');
            grid.className = 'media-grid';
            all.forEach(a => {
                const item = document.createElement('a');
                item.className = 'media-item';
                item.href = a.url;
                item.target = '_blank';
                const isImg = (a.type || '').startsWith('image/');
                item.innerHTML = isImg
                    ? `<img src="${a.url}" alt="${a.name || 'mídia'}"/>`
                    : `<div class="media-file"><i class="bi bi-file-earmark"></i><span>${a.name || 'arquivo'}</span></div>`;
                grid.appendChild(item);
            });
            mediaBox.innerHTML = '';
            mediaBox.appendChild(grid);
        }).catch(() => {
            mediaBox.innerHTML = '<p class="text-muted">Falha ao carregar mídias.</p>';
        });
    }

    async startCall(kind = 'video') {
        if (!this.currentId || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            alert('Abra uma conversa antes de iniciar chamada.');
            return;
        }
        const callModal = document.getElementById('call-modal');
        const localVideo = document.getElementById('local-video');
        const remoteVideo = document.getElementById('remote-video');
        if (!callModal || !localVideo || !remoteVideo) return;

        callModal.style.display = 'flex';
        this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: kind === 'video' });
        localVideo.srcObject = this.localStream;

        this.pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
        this.localStream.getTracks().forEach(t => this.pc.addTrack(t, this.localStream));
        this.remoteStream = new MediaStream();
        remoteVideo.srcObject = this.remoteStream;
        this.pc.ontrack = (ev) => ev.streams[0].getTracks().forEach(t => this.remoteStream.addTrack(t));
        this.pc.onicecandidate = (ev) => {
            if (ev.candidate) this.ws.send(JSON.stringify({ action: 'call_ice', data: { candidate: ev.candidate } }));
        };

        const offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);
        this.ws.send(JSON.stringify({ action: 'call_offer', data: { sdp: offer, kind } }));
    }

    async handleCallSignal(payload) {
        const action = payload.action;
        const data = payload.data || {};
        const fromMe = (payload.from && payload.from === (window.userName || window.username || ''));
        const callModal = document.getElementById('call-modal');
        const localVideo = document.getElementById('local-video');
        const remoteVideo = document.getElementById('remote-video');

        if (fromMe && action !== 'call_end') return;

        if (action === 'call_offer') {
            if (callModal) callModal.style.display = 'flex';
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: !!(data.kind === 'video') });
            if (localVideo) localVideo.srcObject = this.localStream;
            this.pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
            this.localStream.getTracks().forEach(t => this.pc.addTrack(t, this.localStream));
            this.remoteStream = new MediaStream();
            if (remoteVideo) remoteVideo.srcObject = this.remoteStream;
            this.pc.ontrack = (ev) => ev.streams[0].getTracks().forEach(t => this.remoteStream.addTrack(t));
            this.pc.onicecandidate = (ev) => {
                if (ev.candidate) this.ws.send(JSON.stringify({ action: 'call_ice', data: { candidate: ev.candidate } }));
            };
            await this.pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
            const answer = await this.pc.createAnswer();
            await this.pc.setLocalDescription(answer);
            this.ws.send(JSON.stringify({ action: 'call_answer', data: { sdp: answer } }));
            return;
        }

        if (action === 'call_answer' && this.pc) {
            await this.pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
            return;
        }

        if (action === 'call_ice' && this.pc && data.candidate) {
            try { await this.pc.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch (e) {}
            return;
        }

        if (action === 'call_end') {
            this.endCall(false);
        }
    }

    toggleMute() {
        if (!this.localStream) return;
        this.localStream.getAudioTracks().forEach(t => { t.enabled = !t.enabled; });
    }

    endCall(sendSignal = true) {
        const callModal = document.getElementById('call-modal');
        if (callModal) callModal.style.display = 'none';
        if (sendSignal && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'call_end', data: {} }));
        }
        if (this.pc) {
            try { this.pc.close(); } catch (e) {}
            this.pc = null;
        }
        if (this.localStream) {
            this.localStream.getTracks().forEach(t => t.stop());
            this.localStream = null;
        }
        this.remoteStream = null;
    }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    window.chatManager = new ChatManager();
});