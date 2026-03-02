(function(){
    function getCookie(name){const v=document.cookie.match('(^|;) ?'+name+'=([^;]*)(;|$)');return v?v[2]:null}
    document.addEventListener('DOMContentLoaded', function(){
        if(typeof window.userId === 'undefined' || !window.userId) return;
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = protocol + window.location.host + '/ws/chat/user-' + window.userId + '/';
        let retries = 0;
        const maxRetries = 10;
        function connectNotifier(){
        try{
            const notifier = new WebSocket(wsUrl);
            notifier.onopen = function(){ retries = 0; console.debug('Notifier socket open'); };
            notifier.onmessage = function(e){
                try{
                    const data = JSON.parse(e.data);
                    // chat_message broadcast will use type 'message' or 'chat_message' depending on source
                    const convIdNum = data.conversation_id ? String(data.conversation_id) : null;
                    // possible DOM data-id values: 'conv-<id>', '<id>', 'pessoa-<id>', 'at-<id>'
                    const sender = data.user || 'Anônimo';
                    const text = data.message || '';
                    // increment global badge
                    const bubbleBadge = document.querySelector('#chatBubble .chat-badge');
                    if(bubbleBadge){
                        let n = parseInt(bubbleBadge.textContent||'0')||0; n = n + 1; bubbleBadge.textContent = n; bubbleBadge.style.display='inline-block';
                    }

                    // refresh panel list when open (keeps recents ordered by latest message)
                    try {
                        if (window.hautomatizeChatPanel && typeof window.hautomatizeChatPanel.refreshList === 'function') {
                            window.hautomatizeChatPanel.refreshList();
                        }
                    } catch (e) {}
                    // attach per-conversation badge in panel if present
                    if(convIdNum){
                        const selectors = [
                            `[data-id="${convIdNum}"]`,
                            `[data-id="conv-${convIdNum}"]`,
                            `[data-id="pessoa-${convIdNum}"]`,
                            `[data-id="at-${convIdNum}"]`
                        ].join(',');
                        const item = document.querySelector(selectors);
                        if(item){
                                // prefer header container for badge
                                const header = item.querySelector('.ig-conversation-header') || item.querySelector('.ig-conversation-info');
                            if(header){
                                let badge = header.querySelector('.local-unread');
                                if(!badge){
                                    badge = document.createElement('span');
                                    badge.className = 'local-unread';
                                    badge.style.cssText = 'background:#dc3545;color:#fff;padding:2px 6px;border-radius:12px;font-size:11px;margin-left:8px;';
                                    header.appendChild(badge);
                                    badge.textContent = '1';
                                } else {
                                    badge.textContent = (parseInt(badge.textContent||'0')+1).toString();
                                }
                            }
                            // move conversation to top of list
                            try {
                                const convs = document.querySelector('.ig-conversations');
                                const firstGroup = convs ? convs.querySelector('.ig-conversation-group') : null;
                                if (firstGroup) firstGroup.insertBefore(item, firstGroup.firstChild);
                            } catch (e) {}
                        }
                    }
                    // optional browser notification
                    if(window.Notification && Notification.permission === 'granted'){
                        new Notification('Nova mensagem', { body: sender+': '+(text.slice(0,120)||'Nova mensagem'), icon: '/static/core/img/default-avatar.svg' });
                    }
                }catch(err){ console.error('Notifier parse', err); }
            };
            notifier.onclose = function(){
                console.debug('Notifier socket closed');
                if (retries < maxRetries) {
                    const wait = Math.min(10000, 500 * Math.pow(2, retries));
                    retries += 1;
                    setTimeout(connectNotifier, wait);
                }
            };
            window.chatNotifierSocket = notifier;
        }catch(e){ console.warn('Notifier init failed', e); }
        }
        connectNotifier();
    });
})();
