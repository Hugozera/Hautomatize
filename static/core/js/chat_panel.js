(function(){
    function getCookie(name) { const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)'); return v ? v[2] : null; }

    document.addEventListener('DOMContentLoaded', function(){
        // reposition chat bubble to middle-right but keep it interactive
        const chatBubble = document.getElementById('chatBubble');
        if(chatBubble){
            chatBubble.style.right = '18px';
            chatBubble.style.top = '50%';
            chatBubble.style.bottom = 'auto';
            chatBubble.style.transform = 'translateY(-50%)';
            chatBubble.style.zIndex = 4500;
        }

        const panel = document.getElementById('globalChatPanel');
        const body = document.getElementById('chat-body');
        const content = document.getElementById('chat-content');
        const input = document.getElementById('chat-input');
        const send = document.getElementById('chat-send');

        function loadLists(){
            content.innerHTML = '<div style="color:#666">Carregando conversas...</div>';
            // load user's recent conversations
            fetch(window.location.origin + '/chat/my_conversations/').then(r=>r.json()).then(json=>{
                content.innerHTML = '';
                const header = document.createElement('div'); header.className='d-flex justify-content-between align-items-center mb-2';
                header.innerHTML = '<strong>Conversas</strong> <a href="#" id="new-conv" class="small">Nova</a>';
                content.appendChild(header);
                const convs = json.conversations || [];
                if(convs.length === 0){
                    const empty = document.createElement('div'); empty.className='text-muted'; empty.innerText = 'Nenhuma conversa recente.'; content.appendChild(empty);
                } else {
                    convs.slice(0,50).forEach(function(c){
                        const el = document.createElement('div'); el.className='mb-2';
                        el.innerHTML = `<a href="#" onclick="openChatInPanel('conv-${c.id}');return false;" class="text-decoration-none">${c.title || '[Conversa]'} <br><small class="text-muted">${c.last_message? c.last_message : ''} ${c.last_time? ' • '+ new Date(c.last_time).toLocaleString():''}</small></a>`;
                        content.appendChild(el);
                    });
                }

                // users header and search slot
                const usersHeader = document.createElement('div'); usersHeader.className='mt-3'; usersHeader.style.fontWeight='600'; usersHeader.innerText='Usuários:'; content.appendChild(usersHeader);
                fetch(window.location.origin + '/api/users/').then(r=>r.json()).then(json2=>{
                    (json2.users||[]).slice(0,50).forEach(function(u){
                        const el = document.createElement('div'); el.className='mb-1';
                        el.innerHTML = `<a href="#" class="text-decoration-none">${u.name}</a>`;
                        content.appendChild(el);
                    });
                }).catch(()=>{ const el=document.createElement('div'); el.innerText='Não foi possível carregar usuários.'; content.appendChild(el); });

                // wire new conversation button
                const newBtn = document.getElementById('new-conv');
                if(newBtn){
                    newBtn.addEventListener('click', function(ev){ ev.preventDefault(); showNewConv(); });
                }
            }).catch(()=>{ content.innerText='Não foi possível carregar conversas.'; });
        }

        function showNewConv(){
            content.innerHTML = '';
            const inp = document.createElement('input'); inp.className='form-control mb-2'; inp.placeholder='Buscar usuário ou empresa...'; content.appendChild(inp);
            const results = document.createElement('div'); results.style.maxHeight='220px'; results.style.overflow='auto'; content.appendChild(results);

            inp.addEventListener('input', function(){
                const q = this.value && this.value.trim(); results.innerHTML = '';
                if(!q) return;
                fetch(window.location.origin + '/api/users/?q='+encodeURIComponent(q)).then(r=>r.json()).then(js=>{
                    (js.users||[]).slice(0,8).forEach(u=>{
                        const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action'; a.innerText = u.name + ' (user)';
                        a.addEventListener('click', function(ev){ ev.preventDefault(); createConvWithUser(u.id, u.name); });
                        results.appendChild(a);
                    });
                });
                fetch(window.location.origin + '/empresas/api/search/?q='+encodeURIComponent(q)).then(r=>r.json()).then(js=>{
                    (js.results||[]).slice(0,8).forEach(e=>{
                        const a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action'; a.innerText = e.nome + ' (empresa)';
                        a.addEventListener('click', function(ev){ ev.preventDefault(); createConvWithEmpresa(e.id, e.nome); });
                        results.appendChild(a);
                    });
                });
            });
        }

        function createConvWithUser(userId, name){
            fetch(window.location.origin + '/chat/create_user_conversation/', {method:'POST', headers:{'X-CSRFToken': getCookie('csrftoken'), 'Content-Type':'application/json'}, body: JSON.stringify({user_id:userId})}).then(r=>r.json()).then(js=>{
                if(js.conversation_id){
                    loadLists();
                    openChatInPanel('conv-'+js.conversation_id);
                }
            });
        }

        function createConvWithEmpresa(empresaId, nome){
            fetch(window.location.origin + '/chat/create_empresa_conversation/', {method:'POST', headers:{'X-CSRFToken': getCookie('csrftoken'), 'Content-Type':'application/json'}, body: JSON.stringify({empresa_id:empresaId})}).then(r=>r.json()).then(js=>{
                if(js.conversation_id){ loadLists(); openChatInPanel('conv-'+js.conversation_id); }
            });
        }

        // Inline chat helpers (open chat inside the panel)
        let currentChatSocket = null;
        let currentChatId = null;

        window.openChatInPanel = function(atendimentoId){
            // close existing
            if(currentChatSocket){ try{ currentChatSocket.close(); }catch(e){} currentChatSocket = null; }
            currentChatId = atendimentoId;
            // prepare UI
            content.innerHTML = '';
            const back = document.createElement('div'); back.className='mb-2'; back.innerHTML = '<a href="#" id="inline-back">← Voltar</a> <span class="ms-2 text-muted">Conectando...</span>';
            content.appendChild(back);
                    const messages = document.createElement('div'); messages.id = 'inline-messages'; messages.style.maxHeight = '220px'; messages.style.overflow = 'auto'; messages.style.paddingTop = '6px'; content.appendChild(messages);

            // wire back
            back.querySelector('#inline-back').addEventListener('click', function(ev){ ev.preventDefault(); closeInlineChat(); loadLists(); });

            // open websocket
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = protocol + window.location.host + '/ws/chat/' + atendimentoId + '/';
            currentChatSocket = new WebSocket(wsUrl);
            currentChatSocket.onopen = function(){ back.querySelector('span').innerText = 'Conectado'; };
                    currentChatSocket.onmessage = function(e){
                try{
                    const data = JSON.parse(e.data);
                            if(data.type === 'message' || (!data.type && data.message)){
                                const item = document.createElement('div'); item.className='chat-msg';
                                const who = document.createElement('div'); who.className = 'who'; who.innerHTML = '<strong>' + (data.user||'Anônimo') + '</strong> <small class="text-muted ms-2">' + (data.created? new Date(data.created).toLocaleTimeString():new Date().toLocaleTimeString()) + '</small>';
                                const body = document.createElement('div'); body.className = 'body'; body.textContent = data.message;
                                item.appendChild(who); item.appendChild(body);
                                messages.appendChild(item);
                                messages.scrollTop = messages.scrollHeight;
                            } else if(data.type === 'presence'){
                        // update presence tooltip on panel
                        const names = (data.users||[]).map(u=>u.username).join(', ');
                        if(names) back.title = names; else back.title = '';
                    }
                }catch(err){ console.error('WS parse', err); }
            };
            currentChatSocket.onclose = function(){ if(back && back.querySelector('span')) back.querySelector('span').innerText = 'Desconectado'; };

            // re-bind send button to send to this chat
            send.onclick = function(){ const v = input.value && input.value.trim(); if(!v || !currentChatSocket) return; currentChatSocket.send(JSON.stringify({message: v})); input.value=''; };
        };

        function closeInlineChat(){ if(currentChatSocket){ try{ currentChatSocket.close(); }catch(e){} currentChatSocket = null; currentChatId = null; } }

        let panelVisible = false;
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

        // default send behavior (if not in inline chat, just append locally)
        if(send){
            send.addEventListener('click', function(){
                if(currentChatSocket){ send.onclick(); return; }
                const v = input.value && input.value.trim(); if(!v) return;
                const el = document.createElement('div'); el.className='chat-msg';
                const who = document.createElement('div'); who.className='who'; who.innerHTML = '<strong>Você:</strong>';
                const body = document.createElement('div'); body.className='body'; body.textContent = v;
                el.appendChild(who); el.appendChild(body);
                content.appendChild(el); input.value=''; body.scrollTop = body.scrollHeight;
            });
        }

    });
})();
