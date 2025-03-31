const DOM = {
    elements: {},
    init: function() {
        this.elements = {
            salvarDriveBtn: document.getElementById('salvar-drive-btn'),
            baixarExcelBtn: document.getElementById('baixar-excel-btn'),
            pastaDriveSelect: document.getElementById('pasta-drive'),
            dataAtualElement: document.getElementById('data-atual'),
            nomeUsuarioElement: document.getElementById('nome-usuario'),
            loadingIndicator: document.getElementById('loading-indicator') // Adicione este elemento no HTML
        };
        return this.elements;
    }
};

document.addEventListener('DOMContentLoaded', function() {
    const {
        salvarDriveBtn,
        baixarExcelBtn,
        pastaDriveSelect,
        dataAtualElement,
        nomeUsuarioElement,
        loadingIndicator
    } = DOM.init();

    // Inicialização
    updateCurrentDate();
    loadCurrentUser();
    loadDriveFolders(); // Carrega as pastas ao iniciar
    setupEventListeners();

    // ============== [FUNÇÕES PRINCIPAIS] ==============
    async function loadDriveFolders() {
        try {
            showLoading();
            const response = await fetch('/api/get_drive_folders');
            const data = await response.json();
            
            if (data.success) {
                pastaDriveSelect.innerHTML = '<option value="">Selecione uma pasta</option>';
                data.folders.forEach(folder => {
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
            
            if (confirm('Deseja limpar as turmas salvas após exportar?')) {
                window.location.href = `/api/export_excel?escola=${encodeURIComponent(escola)}&auto_clear=true`;
            } else {
                window.location.href = `/api/export_excel?escola=${encodeURIComponent(escola)}`;
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