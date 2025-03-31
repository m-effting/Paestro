const DOM = {
    elements: {},
    init: function() {
        this.elements = {
            salvarDriveBtn: document.getElementById('salvar-drive-btn'),
            baixarExcelBtn: document.getElementById('baixar-excel-btn'),
            pastaDriveSelect: document.getElementById('pasta-drive'),
            customSelectInput: document.querySelector('.custom-select-input'),
            customSelectDropdown: document.querySelector('.custom-select-dropdown'),
            customSelectClear: document.querySelector('.custom-select-clear'),
            customSelectArrow: document.querySelector('.custom-select-arrow'),
            dataAtualElement: document.getElementById('data-atual'),
            nomeUsuarioElement: document.getElementById('nome-usuario'),
            loadingIndicator: document.getElementById('loading-indicator')
        };
        return this.elements;
    }
};

document.addEventListener('DOMContentLoaded', function() {
    const {
        salvarDriveBtn,
        baixarExcelBtn,
        pastaDriveSelect,
        customSelectInput,
        customSelectDropdown,
        customSelectClear,
        customSelectArrow,
        dataAtualElement,
        nomeUsuarioElement,
        loadingIndicator
    } = DOM.init();

    let folders = []; // Store the folder list for filtering

    // Inicialização
    updateCurrentDate();
    loadCurrentUser();
    loadDriveFolders();
    setupEventListeners();

    // ============== [FUNÇÕES PRINCIPAIS] ==============
    async function loadDriveFolders() {
        try {
            showLoading();
            const response = await fetch('/api/get_drive_folders');
            const data = await response.json();
            
            if (data.success) {
                folders = data.folders; // Store folders for filtering
                populateDropdown(folders); // Populate the dropdown initially
                // Populate the hidden select for form submission
                pastaDriveSelect.innerHTML = '';
                folders.forEach(folder => {
                    const option = new Option(folder.name, folder.id);
                    pastaDriveSelect.add(option);
                });
            } else {
                showError('Erro ao carregar pastas: ' + (data.error || 'Desconhecido'));
            }
        } catch (error) {
            showError('Falha na conexão: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    function populateDropdown(folderList) {
        customSelectDropdown.innerHTML = '';
        folderList.forEach(folder => {
            const option = document.createElement('div');
            option.classList.add('custom-select-option');
            option.textContent = folder.name;
            option.dataset.value = folder.id;
            option.addEventListener('click', () => {
                selectOption(folder);
            });
            customSelectDropdown.appendChild(option);
        });
    }

    function selectOption(folder) {
        customSelectInput.value = folder.name;
        pastaDriveSelect.value = folder.id; // Update the hidden select
        customSelectDropdown.style.display = 'none';
        customSelectClear.style.display = 'inline-block';
    }

    async function salvarNoDrive() {
        const pastaSelecionada = pastaDriveSelect.value;
        const escola = sessionStorage.getItem('escola_selecionada');
        const periodo = document.querySelector('input[name="periodo"]:checked')?.value || '';

        if (!pastaSelecionada) {
            return showError('Selecione uma pasta do Drive!');
        }

        try {
            showLoading();
            const response = await fetch('/api/export_excel_drive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_id: pastaSelecionada,
                    escola: escola,
                    periodo: periodo
                })
            });
            
            const result = await response.json();
            if (result.success) {
                alert(`✅ Arquivo salvo no Drive!\nID: ${result.drive_file_id}`);
                sessionStorage.removeItem('escola_selecionada');
            } else {
                showError(result.error || 'Erro desconhecido');
            }
        } catch (error) {
            showError('Erro na requisição: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    // ============== [FUNÇÕES AUXILIARES] ==============
    function showLoading() {
        loadingIndicator.style.display = 'block';
        salvarDriveBtn.disabled = true;
        baixarExcelBtn.disabled = true;
    }

    function hideLoading() {
        loadingIndicator.style.display = 'none';
        salvarDriveBtn.disabled = false;
        baixarExcelBtn.disabled = false;
    }

    function showError(message) {
        alert('❌ ' + message);
        console.error(message);
    }

    function updateCurrentDate() {
        dataAtualElement.textContent = new Date().toLocaleDateString('pt-BR');
    }

    async function loadCurrentUser() {
        try {
            const response = await fetch('/api/get_current_user');
            const data = await response.json();
            nomeUsuarioElement.textContent = data.username || 'Usuário não identificado';
        } catch (error) {
            console.error('Erro ao carregar usuário:', error);
        }
    }

    function setupEventListeners() {
        salvarDriveBtn.addEventListener('click', salvarNoDrive);
        
        baixarExcelBtn.addEventListener('click', () => {
            const escola = sessionStorage.getItem('escola_selecionada');
            if (!escola) {
                showError('Nenhuma escola selecionada. Volte à página de chamada e selecione uma escola primeiro.');
                return;
            }
            
            if (confirm('As turmas salvas serão limpas após exportar.')) {
                window.location.href = `/api/export_excel?escola=${encodeURIComponent(escola)}&auto_clear=true`;
            } else {
                window.location.href = `/api/export_excel?escola=${encodeURIComponent(escola)}`;
            }
        });

        // Custom select input event listeners
        customSelectInput.addEventListener('input', () => {
            const searchTerm = customSelectInput.value.toLowerCase();
            const filteredFolders = folders.filter(folder => 
                folder.name.toLowerCase().includes(searchTerm)
            );
            populateDropdown(filteredFolders);
            customSelectDropdown.style.display = 'block';
        });

        customSelectInput.addEventListener('focus', () => {
            customSelectDropdown.style.display = 'block';
            populateDropdown(folders);
        });

        customSelectInput.addEventListener('blur', () => {
            setTimeout(() => {
                customSelectDropdown.style.display = 'none';
            }, 200);
        });

        customSelectClear.addEventListener('click', () => {
            customSelectInput.value = '';
            pastaDriveSelect.value = '';
            customSelectClear.style.display = 'none';
            populateDropdown(folders);
        });

        customSelectArrow.addEventListener('click', () => {
            customSelectDropdown.style.display = 
                customSelectDropdown.style.display === 'block' ? 'none' : 'block';
            if (customSelectDropdown.style.display === 'block') {
                populateDropdown(folders);
                customSelectInput.focus();
            }
        });

        // Verificar periodicamente se há turmas salvas
        setInterval(async () => {
            try {
                const response = await fetch('/api/get_saved_classes_status');
                const data = await response.json();
                if (data.success && data.saved_classes.length === 0) {
                    baixarExcelBtn.disabled = true;
                } else {
                    baixarExcelBtn.disabled = false;
                }
            } catch (error) {
                console.error('Erro ao verificar turmas:', error);
            }
        }, 3000);
    }
});