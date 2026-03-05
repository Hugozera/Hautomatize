// JavaScript para o formulário de pessoa com gerenciamento visual de permissões

document.addEventListener('DOMContentLoaded', function() {
    // ============================================================================
    // AVATAR UPLOAD - Drag & Drop + Preview
    // ============================================================================
    const avatarDrop = document.getElementById('avatarDrop');
    const avatarPreview = document.getElementById('avatarPreview');
    const fotoBrowser = document.getElementById('id_foto_custom');

    if (avatarDrop && fotoBrowser) {
        // Click to upload
        avatarDrop.addEventListener('click', () => fotoBrowser.click());

        // Drag & drop
        avatarDrop.addEventListener('dragover', (e) => {
            e.preventDefault();
            avatarDrop.classList.add('drag-over');
        });

        avatarDrop.addEventListener('dragleave', () => {
            avatarDrop.classList.remove('drag-over');
        });

        avatarDrop.addEventListener('drop', (e) => {
            e.preventDefault();
            avatarDrop.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });

        // File input change
        fotoBrowser.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });

        function handleFileSelect(file) {
            if (file.type.startsWith('image/')) {
                // Validar tamanho (máximo 2MB)
                const maxSize = 2 * 1024 * 1024; // 2MB
                if (file.size > maxSize) {
                    alert('⚠️ Arquivo muito grande! Tamanho máximo: 2 MB\nTamanho do arquivo: ' + (file.size / 1024 / 1024).toFixed(2) + ' MB');
                    return;
                }
                
                // Validar tipo
                const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
                if (!allowedTypes.includes(file.type)) {
                    alert('⚠️ Formato não permitido!\nFormatos aceitos: JPG, PNG, WEBP');
                    return;
                }
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    avatarPreview.src = e.target.result;
                    // Garantir que preview não fica muito grande
                    avatarPreview.style.maxWidth = '120px';
                    avatarPreview.style.maxHeight = '120px';
                    avatarPreview.style.width = '120px';
                    avatarPreview.style.height = '120px';
                    avatarPreview.style.objectFit = 'cover';
                };
                reader.readAsDataURL(file);
            } else {
                alert('⚠️ Por favor selecione uma imagem válida');
            }
        }
    }

    // ============================================================================
    // PASSWORD STRENGTH METER
    // ============================================================================
    const passwordField = document.getElementById('id_password');
    const pwMeter = document.getElementById('pwFill');
    const pwText = document.getElementById('pwText');

    if (passwordField && pwMeter) {
        passwordField.addEventListener('input', () => {
            const password = passwordField.value;
            const strength = calculatePasswordStrength(password);
            updateMeter(strength);
        });

        function calculatePasswordStrength(password) {
            let score = 0;
            if (password.length >= 8) score += 20;
            if (password.length >= 12) score += 10;
            if (/[a-z]/.test(password)) score += 15;
            if (/[A-Z]/.test(password)) score += 15;
            if (/[0-9]/.test(password)) score += 15;
            if (/[^a-zA-Z0-9]/.test(password)) score += 25;
            return Math.min(score, 100);
        }

        function updateMeter(strength) {
            pwMeter.style.width = strength + '%';
            
            if (strength < 30) {
                pwMeter.style.background = 'linear-gradient(90deg, #ff6b6b, #ff9a9a)';
                pwText.textContent = 'Fraca';
                pwText.style.color = '#ff6b6b';
            } else if (strength < 60) {
                pwMeter.style.background = 'linear-gradient(90deg, #ffa502, #ffb84d)';
                pwText.textContent = 'Regular';
                pwText.style.color = '#ffa502';
            } else if (strength < 85) {
                pwMeter.style.background = 'linear-gradient(90deg, #48bb78, #68d391)';
                pwText.textContent = 'Boa';
                pwText.style.color = '#48bb78';
            } else {
                pwMeter.style.background = 'linear-gradient(90deg, #2196F3, #42a5f5)';
                pwText.textContent = 'Excelente';
                pwText.style.color = '#2196F3';
            }
        }
    }

    // ============================================================================
    // MODULE TOGGLE - Expandir/Recolher módulos com animação
    // ============================================================================
    const moduleToggles = document.querySelectorAll('.module-toggle');
    
    moduleToggles.forEach(toggle => {
        const icon = toggle.querySelector('.module-toggle-icon');
        const moduleGroup = toggle.nextElementSibling;

        if (moduleGroup && moduleGroup.classList.contains('module-group')) {
            // Check se há checkboxes selecionadas
            const hasChecked = moduleGroup.querySelectorAll('input[type="checkbox"]:checked').length > 0;
            
            toggle.addEventListener('click', function(e) {
                // Se clicou na checkbox, não toggle
                if (e.target.type === 'checkbox') return;
                
                if (moduleGroup.classList.contains('expanded')) {
                    moduleGroup.classList.remove('expanded');
                    if (icon) icon.style.transform = 'rotate(0deg)';
                } else {
                    moduleGroup.classList.add('expanded');
                    if (icon) icon.style.transform = 'rotate(90deg)';
                }
            });

            // Clique na label também deve expandir
            toggle.addEventListener('click', function(e) {
                if (e.target.tagName === 'LABEL' || e.target.tagName === 'SPAN') {
                    if (moduleGroup.classList.contains('expanded')) {
                        moduleGroup.classList.remove('expanded');
                        if (icon) icon.style.transform = 'rotate(0deg)';
                    } else {
                        moduleGroup.classList.add('expanded');
                        if (icon) icon.style.transform = 'rotate(90deg)';
                    }
                }
            });
        }
    });

    function setPermItemVisualState(permCheckbox) {
        const permItem = permCheckbox.closest('.perm-item');
        if (permItem) {
            permItem.classList.toggle('selected', permCheckbox.checked);
        }
    }

    function updateModuleVisualState(moduleContainer) {
        if (!moduleContainer) return;
        const moduleCheckbox = moduleContainer.querySelector('.module-checkbox');
        const moduleHeader = moduleContainer.querySelector('.module-header');
        const allPerms = moduleContainer.querySelectorAll('.perm-checkbox');
        const checkedPerms = moduleContainer.querySelectorAll('.perm-checkbox:checked');

        if (!moduleCheckbox || allPerms.length === 0) return;

        moduleCheckbox.checked = checkedPerms.length > 0 && checkedPerms.length === allPerms.length;
        moduleCheckbox.indeterminate = checkedPerms.length > 0 && checkedPerms.length < allPerms.length;

        if (moduleHeader) {
            moduleHeader.classList.toggle('module-selected', moduleCheckbox.checked);
            moduleHeader.classList.toggle('module-partial', moduleCheckbox.indeterminate);
        }
    }

    // ============================================================================
    // MODULE CHECKBOX - Selecionar/Desselecionar todas as permissões do módulo
    // ============================================================================
    const moduleCheckboxes = document.querySelectorAll('.module-checkbox');
    
    moduleCheckboxes.forEach(checkbox => {
        const moduleContainer = checkbox.closest('.module-container');
        if (moduleContainer) {
            updateModuleVisualState(moduleContainer);
        }

        checkbox.addEventListener('change', function() {
            const moduleGroup = this.closest('.module-container').querySelector('.module-group');
            if (moduleGroup) {
                const permCheckboxes = moduleGroup.querySelectorAll('.perm-checkbox');
                permCheckboxes.forEach(perm => {
                    perm.checked = this.checked;
                    setPermItemVisualState(perm);
                });
            }
            updateModuleVisualState(this.closest('.module-container'));
            updatePermissionSummary();
        });
    });

    // ============================================================================
    // PERMISSION CHECKBOX - Sync com permissões individuais
    // ============================================================================
    const permCheckboxes = document.querySelectorAll('.perm-checkbox');

    permCheckboxes.forEach(setPermItemVisualState);
    
    permCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updatePermissionSummary();
            setPermItemVisualState(this);
            
            // Update module checkbox if all perms are selected/partial
            const moduleGroup = this.closest('.module-group');
            if (moduleGroup) {
                const moduleContainer = moduleGroup.closest('.module-container');
                updateModuleVisualState(moduleContainer);
            }
        });
    });

    // ============================================================================
    // SEARCH FILTER - Filtrar permissões por busca
    // ============================================================================
    const permSearch = document.getElementById('permSearch');
    
    if (permSearch) {
        permSearch.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const modules = document.querySelectorAll('.module-container');
            let visibleModules = 0;

            modules.forEach(module => {
                const moduleGroup = module.querySelector('.module-group');
                const permItems = moduleGroup ? moduleGroup.querySelectorAll('.perm-item') : [];
                let visiblePerms = 0;

                permItems.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    if (text.includes(searchTerm)) {
                        item.style.display = 'flex';
                        visiblePerms++;
                    } else {
                        item.style.display = 'none';
                    }
                });

                if (visiblePerms > 0) {
                    module.style.display = 'block';
                    visibleModules++;
                    // Auto-expand when searching
                    if (searchTerm.length > 0) {
                        const moduleGroup = module.querySelector('.module-group');
                        moduleGroup.classList.add('expanded');
                        const icon = module.querySelector('.module-toggle-icon');
                        if (icon) icon.style.transform = 'rotate(90deg)';
                    }
                } else {
                    module.style.display = 'none';
                }
            });

            // Mostrar mensagem se nada encontrado
            const container = document.getElementById('permissions-container');
            if (visibleModules === 0 && searchTerm.length > 0) {
                if (!document.getElementById('no-results-message')) {
                    const noResults = document.createElement('div');
                    noResults.id = 'no-results-message';
                    noResults.className = 'alert alert-info mt-3';
                    noResults.innerHTML = '<i class="bi bi-info-circle me-2"></i>Nenhuma permissão encontrada para "<strong>' + searchTerm + '</strong>"';
                    container.appendChild(noResults);
                }
            } else {
                const noResults = document.getElementById('no-results-message');
                if (noResults) noResults.remove();
            }
        });
    }

    // ============================================================================
    // EXPAND/COLLAPSE ALL BUTTONS
    // ============================================================================
    const expandAllBtn = document.getElementById('expandAllBtn');
    const collapseAllBtn = document.getElementById('collapseAllBtn');

    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.module-group').forEach(group => {
                group.classList.add('expanded');
            });
            document.querySelectorAll('.module-toggle-icon').forEach(icon => {
                icon.style.transform = 'rotate(90deg)';
            });
        });
    }

    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.module-group').forEach(group => {
                group.classList.remove('expanded');
            });
            document.querySelectorAll('.module-toggle-icon').forEach(icon => {
                icon.style.transform = 'rotate(0deg)';
            });
        });
    }

    // ============================================================================
    // PERMISSION SUMMARY - Atualizar badges com contadores
    // ============================================================================
    function updatePermissionSummary() {
        const selectedPerms = document.querySelectorAll('.perm-checkbox:checked').length;
        const totalPerms = document.querySelectorAll('.perm-checkbox').length;

        const selectedPermsCount = document.getElementById('selectedPermsCount');
        const totalPermsCount = document.getElementById('totalPermsCount');

        if (selectedPermsCount) selectedPermsCount.textContent = selectedPerms;
        if (totalPermsCount) totalPermsCount.textContent = totalPerms;
    }

    // Initial summary update
    updatePermissionSummary();

    // ============================================================================
    // FORM VALIDATION
    // ============================================================================
    const form = document.querySelector('form.needs-validation');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Validação de senha
            const password = document.getElementById('id_password');
            const passwordConfirm = document.getElementById('id_password_confirm');
            
            if (password && passwordConfirm && password.value !== passwordConfirm.value) {
                e.preventDefault();
                e.stopPropagation();
                alert('As senhas não conferem!');
                return false;
            }

            // Validação de username
            const username = document.getElementById('id_username');
            if (username && username.value.length < 3) {
                e.preventDefault();
                e.stopPropagation();
                username.focus();
                alert('O nome de usuário deve ter pelo menos 3 caracteres');
                return false;
            }
        });
    }

    // ============================================================================
    // INICIALIZAÇÃO
    // ============================================================================
    console.log('✅ Form JavaScript loaded successfully');
});
