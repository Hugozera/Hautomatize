(function(){
    function getCookie(name) { const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)'); return v ? v[2] : null; }

    document.addEventListener('DOMContentLoaded', function(){
        const chatBubble = document.getElementById('chatBubble');
        const panel = document.getElementById('globalChatPanel');
        const body = document.getElementById('chat-body');
        const content = document.getElementById('chat-content');
        const input = document.getElementById('chat-input');
        const send = document.getElementById('chat-send');

        if(!chatBubble || !panel || !body || !content || !input || !send) return;

        let panelVisible = false;
        let currentRoom = null;
        let currentSocket = null;
        let latestConversations = [];

        function closeSocket(){
            if(currentSocket){
                try{ currentSocket.close(); } catch(e){}
                currentSocket = null;
            }
        }

        function roomWsPath(room){
            if(String(room).startsWith('at-')) return '/ws/atendimento/' + String(room).replace('at-','') + '/';
            return '/ws/chat/' + room + '/';
        }

        function renderMessage(msg){
            const wrap = document.createElement('div');
            wrap.className = 'hp-msg ' + (msg.own ? 'own' : 'other');
            const head = document.createElement('div');
            head.className = 'hp-msg-head';
            head.innerHTML = '<strong>' + (msg.user || 'Anônimo') + '</strong><span>' + (msg.time || '') + '</span>';
            const bodyEl = document.createElement('div');
            bodyEl.className = 'hp-msg-body';
            bodyEl.textContent = msg.message || '';
            wrap.appendChild(head);
            wrap.appendChild(bodyEl);
            return wrap;
        }

        function loadHistory(room){
            const messagesBox = document.getElementById('inline-messages');
            if(!messagesBox) return;
            messagesBox.innerHTML = '<div class="hp-loading">Carregando histórico...</div>';
            fetch(window.location.origin + '/api/messages/' + room + '/')
                .then(r => r.ok ? r.json() : [])
                .then(list => {
                    messagesBox.innerHTML = '';
                    (list || []).forEach(m => messagesBox.appendChild(renderMessage(m)));
                    messagesBox.scrollTop = messagesBox.scrollHeight;
                })
                .catch(() => {
                    messagesBox.innerHTML = '<div class="hp-loading">Não foi possível carregar mensagens.</div>';
                });
        }

        function bindSend(){
            send.onclick = function(){
                const v = (input.value || '').trim();
                if(!v || !currentSocket || currentSocket.readyState !== WebSocket.OPEN) return;
                currentSocket.send(JSON.stringify({message: v}));
                input.value = '';
            };
        }

        function renderConversationList(filterText){
            const listWrap = document.querySelector('.hp-conv-list');
            if(!listWrap) return;
            const query = (filterText || '').trim().toLowerCase();
            listWrap.innerHTML = '';

            const convs = (latestConversations || []).filter(c => {
                if(!query) return true;
                const hay = ((c.title || '') + ' ' + (c.last_message || '')).toLowerCase();
                return hay.includes(query);
            });

            if(convs.length === 0){
                const empty = document.createElement('div');
                empty.className = 'hp-loading';
                empty.innerText = query ? 'Nenhum chat encontrado.' : 'Nenhuma conversa recente.';
                listWrap.appendChild(empty);
                return;
            }

            convs.slice(0,80).forEach(function(c){
                const roomId = 'conv-' + c.id;
                const el = document.createElement('button');
                el.type = 'button';
                el.className = 'hp-conv-item' + (currentRoom === roomId ? ' active' : '');
                el.innerHTML = `
                    <div class="hp-conv-main">${c.title || '[Conversa]'}</div>
                    <div class="hp-conv-sub">${c.last_message ? c.last_message : 'Sem mensagens'} ${c.last_time ? ' • ' + new Date(c.last_time).toLocaleString() : ''}</div>
                `;
                el.addEventListener('click', function(){ openChatInPanel(roomId, c.title || 'Conversa'); });
                listWrap.appendChild(el);
            });
        }

        function loadLists(){
            currentRoom = null;
            closeSocket();
            input.placeholder = 'Selecione uma conversa para enviar...';
            input.disabled = true;
            send.disabled = true;

            content.innerHTML = '<div class="hp-loading">Carregando conversas...</div>';
            fetch(window.location.origin + '/chat/my_conversations/').then(r=>r.json()).then(json=>{
                content.innerHTML = '';
                const header = document.createElement('div');
                header.className = 'hp-list-header';
                header.innerHTML = '<strong>Conversas recentes</strong> <a href="#" id="new-conv">Nova</a>';
                content.appendChild(header);

                const search = document.createElement('input');
                search.type = 'text';
                search.className = 'form-control form-control-sm hp-conv-search';
                search.placeholder = 'Buscar conversa...';
                content.appendChild(search);

                const listWrap = document.createElement('div');
                listWrap.className = 'hp-conv-list';
                content.appendChild(listWrap);

                latestConversations = json.conversations || [];
                renderConversationList('');
                search.addEventListener('input', function(){ renderConversationList(search.value); });

                const newBtn = document.getElementById('new-conv');
                if(newBtn){
                    newBtn.addEventListener('click', function(ev){ ev.preventDefault(); showNewConv(); });
                }
            }).catch(()=>{ content.innerText='Não foi possível carregar conversas.'; });
        }

        function showNewConv(){
            content.innerHTML = '';
            const inp = document.createElement('input'); inp.className='form-control mb-2'; inp.placeholder='Buscar usuário ou empresa...'; content.appendChild(inp);
            const results = document.createElement('div'); results.className = 'hp-conv-list'; content.appendChild(results);

            inp.addEventListener('input', function(){
                const q = this.value && this.value.trim(); results.innerHTML = '';
                if(!q) return;
                fetch(window.location.origin + '/api/users/?q='+encodeURIComponent(q)).then(r=>r.json()).then(js=>{
                    (js.users||[]).slice(0,8).forEach(u=>{
                        const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action hp-new-item'; a.innerText = u.name;
                        a.addEventListener('click', function(ev){ ev.preventDefault(); createConvWithUser(u.id, u.name); });
                        results.appendChild(a);
                    });
                });
                fetch(window.location.origin + '/empresas/api/search/?q='+encodeURIComponent(q)).then(r=>r.json()).then(js=>{
                    (js.results||[]).slice(0,8).forEach(e=>{
                        const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action hp-new-item'; a.innerText = e.nome + ' (empresa)';
                        a.addEventListener('click', function(ev){ ev.preventDefault(); createConvWithEmpresa(e.id, e.nome); });
                        results.appendChild(a);
                    });
                });
            });
        }

        function createConvWithUser(userId, name){
            fetch(window.location.origin + '/chat/create_user_conversation/', {method:'POST', headers:{'X-CSRFToken': getCookie('csrftoken'), 'Content-Type':'application/json'}, body: JSON.stringify({user_id:userId})}).then(r=>r.json()).then(js=>{
                if(js.conversation_id){
                    openChatInPanel('conv-'+js.conversation_id, name || 'Conversa');
                }
            });
        }

        function createConvWithEmpresa(empresaId, nome){
            fetch(window.location.origin + '/chat/create_empresa_conversation/', {method:'POST', headers:{'X-CSRFToken': getCookie('csrftoken'), 'Content-Type':'application/json'}, body: JSON.stringify({empresa_id:empresaId})}).then(r=>r.json()).then(js=>{
                if(js.conversation_id){ openChatInPanel('conv-'+js.conversation_id, nome || 'Empresa'); }
            });
        }

        window.openChatInPanel = function(roomId, title){
            currentRoom = roomId;
            closeSocket();
            input.disabled = false;
            send.disabled = false;
            input.placeholder = 'Digite uma mensagem...';

            content.innerHTML = '';
            const back = document.createElement('div');
            back.className = 'hp-chat-head';
            back.innerHTML = '<a href="#" id="inline-back">← Conversas</a><div><strong>' + (title || 'Conversa') + '</strong> <span id="inline-state" class="text-muted ms-2">Conectando...</span></div>';
            content.appendChild(back);
            const messages = document.createElement('div');
            messages.id = 'inline-messages';
            messages.className = 'hp-messages';
            content.appendChild(messages);

            back.querySelector('#inline-back').addEventListener('click', function(ev){ ev.preventDefault(); closeInlineChat(); loadLists(); });
            loadHistory(roomId);

            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            currentSocket = new WebSocket(protocol + window.location.host + roomWsPath(roomId));
            currentSocket.onopen = function(){ const st = document.getElementById('inline-state'); if(st) st.innerText = 'Conectado'; };
            currentSocket.onmessage = function(e){
                try{
                    const data = JSON.parse(e.data);
                    if(data.type === 'message' || (!data.type && data.message)){
                        messages.appendChild(renderMessage({
                            user: data.user || 'Anônimo',
                            message: data.message || '',
                            time: data.created ? new Date(data.created).toLocaleTimeString() : new Date().toLocaleTimeString(),
                            own: (data.user === (window.userName || window.username || '')),
                        }));
                        messages.scrollTop = messages.scrollHeight;
                    }
                }catch(err){ console.error('WS parse', err); }
            };
            currentSocket.onclose = function(){ const st = document.getElementById('inline-state'); if(st) st.innerText = 'Desconectado'; };
            bindSend();
            input.focus();
        };

        function closeInlineChat(){ closeSocket(); currentRoom = null; }

        function showPanel(){ panel.style.display='block'; panelVisible=true; loadLists(); }
        function hidePanel(){ panel.style.display='none'; panelVisible=false; }

        if(document.getElementById('chatBubble')){
            document.getElementById('chatBubble').addEventListener('click', function(e){
                e.preventDefault();
                if(panelVisible) hidePanel(); else showPanel();
            });
        }
        if(document.getElementById('chat-close')) document.getElementById('chat-close').addEventListener('click', hidePanel);
        if(document.getElementById('chat-minimize')) document.getElementById('chat-minimize').addEventListener('click', function(){
            if(body.style.display === 'none'){ body.style.display='block'; input.style.display='inline-block'; send.style.display='inline-block'; }
            else { body.style.display='none'; input.style.display='none'; send.style.display='none'; }
        });

        bindSend();
        input.addEventListener('keydown', function(ev){
            if(ev.key === 'Enter' && !ev.shiftKey){
                ev.preventDefault();
                send.click();
            }
        });

        // expose helpers for notifier/live updates
        window.hautomatizeChatPanel = {
            refreshList: function(){ if(panelVisible && !currentRoom) loadLists(); },
            openRoom: function(roomId, title){
                if(!panelVisible){ panel.style.display='block'; panelVisible = true; }
                window.openChatInPanel(roomId, title || 'Conversa');
            }
        };

    });
})();
