document.addEventListener('DOMContentLoaded', function() {
    // --- Elementos UI ---
    const dropArea = document.getElementById('upload-droparea');
    const fileInput = document.getElementById('file-input');
    const selectedFilesContainer = document.getElementById('selected-files');
    const uploadBtn = document.getElementById('upload-btn');
    const fileControls = document.getElementById('file-controls');
    const fileCountLabel = document.getElementById('file-count');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPercentage = document.getElementById('progress-percentage');
    
    // Lista para acumular arquivos (Objeto File)
    let accumulatedFiles = [];

    // --- Inicialização ---
    fetchUserInfo();

    // --- Eventos Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false);
    });

    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // --- Evento Input File ---
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
        this.value = '';
    });

    // --- Gerenciamento de Arquivos ---
    function handleFiles(files) {
        Array.from(files).forEach(file => {
            if (file.name.match(/\.xlsx|\.xls$/i)) {
                const exists = accumulatedFiles.some(f => f.name === file.name);
                if (!exists) {
                    accumulatedFiles.push(file);
                    addFileToDisplay(file);
                }
            }
        });
        updateUIState();
    }

    function addFileToDisplay(file) {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'file-item';
        
        // Ícone diferente para provável arquivo de análise
        let iconClass = 'fa-file-excel';
        if (!file.name.match(/\d{2}-\d{2}-\d{4}/) && !file.name.match(/\d{2}-\d{2}-\d{2}/)) {
            iconClass = 'fa-chart-pie'; 
        }

        fileDiv.innerHTML = `
            <div class="file-info">
                <i class="fas ${iconClass}"></i>
                <span class="file-name">${file.name}</span>
            </div>
            <button type="button" class="remove-file" aria-label="Remover">&times;</button>
        `;

        fileDiv.querySelector('.remove-file').addEventListener('click', function() {
            accumulatedFiles = accumulatedFiles.filter(f => f.name !== file.name);
            fileDiv.remove();
            updateUIState();
        });

        selectedFilesContainer.appendChild(fileDiv);
    }

    function updateUIState() {
        if (accumulatedFiles.length > 0) {
            fileControls.style.display = 'block'; 
            fileCountLabel.textContent = `${accumulatedFiles.length} arquivo(s)`;
            uploadBtn.disabled = false;
        } else {
            fileControls.style.display = 'none';
            uploadBtn.disabled = true;
        }
    }

    window.limparTodosArquivos = function() {
        accumulatedFiles = [];
        selectedFilesContainer.innerHTML = '';
        updateUIState();
    };

    const clearBtn = document.getElementById('clear-files-btn');
    if(clearBtn) clearBtn.addEventListener('click', window.limparTodosArquivos);

    // --- Envio e Geração ---
    uploadBtn.addEventListener('click', function() {
        if (accumulatedFiles.length === 0) return;

        // Validação de checkboxes
        const genExcel = document.getElementById('check-excel').checked;
        const genPdf = document.getElementById('check-pdf').checked;

        if (!genExcel && !genPdf) {
            showModal('Aviso', 'Selecione pelo menos um formato para gerar (Excel ou PDF).');
            return;
        }

        progressContainer.style.display = 'block';
        uploadBtn.disabled = true;
        updateProgress(10, 'Enviando arquivos...');

        const formData = new FormData();
        accumulatedFiles.forEach(file => {
            formData.append('files[]', file);
        });

        fetch('/process_report_files', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) throw new Error('Erro no upload dos arquivos');
            return response.json();
        })
        .then(data => {
            if (!data.success) throw new Error(data.error || 'Erro no processamento');
            
            updateProgress(50, 'Arquivos recebidos. Consolidando dados...');
            
            return fetch('/generate_consolidated_report', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    file_paths: data.file_paths,
                    user_id: data.user_id,
                    generate_excel: genExcel,
                    generate_pdf: genPdf
                })
            });
        })
        .then(response => {
            if (!response.ok) throw new Error('Erro na geração do relatório');
            return response.json();
        })
        .then(data => {
            if (!data.success) throw new Error(data.error || "Erro desconhecido ao gerar relatório");

            updateProgress(100, 'Concluído!');
            console.log("Download URL:", data.download_url);
            
            if (data.download_url) {
                // Inicia download
                window.location.href = data.download_url;
                showModal('Sucesso', 'Relatório gerado! O download deve começar automaticamente.');
            } else {
                throw new Error("URL de download não recebida.");
            }

            // Limpeza após sucesso
            setTimeout(() => {
                progressContainer.style.display = 'none';
                updateProgress(0, '');
                window.limparTodosArquivos();
            }, 3000);
        })
        .catch(error => {
            console.error("Erro Relatório:", error);
            progressContainer.style.display = 'none';
            uploadBtn.disabled = false;
            showModal('Erro', error.message || 'Falha ao processar relatório.');
        });
    });

    function updateProgress(percent, text) {
        progressFill.style.width = percent + '%';
        progressPercentage.textContent = percent + '%';
        if (text) progressText.textContent = text;
    }

    function fetchUserInfo() {
        fetch('/api/get_current_user')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const nameEl = document.getElementById('nome-usuario');
                    const periodEl = document.getElementById('periodo-usuario');
                    if(nameEl) nameEl.textContent = data.username || 'Visitante';
                    if(periodEl) periodEl.textContent = data.periodo || '';
                }
            })
            .catch(console.error);
    }

    if (!window.showModal) {
        window.showModal = function(title, msg) {
            alert(`${title}: ${msg}`);
        };
    }
});