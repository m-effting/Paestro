document.addEventListener('DOMContentLoaded', function() {
    // Função para mostrar modal (necessária para o sistema)
    function showModal(title, message) {
        alert(title + ': ' + message);
    }
    
    // Torna a função showModal disponível globalmente
    window.showModal = showModal;
    
    // Elementos UI
    const dropArea = document.getElementById('upload-droparea');
    const fileInput = document.getElementById('file-input');
    const selectedFiles = document.getElementById('selected-files');
    const uploadBtn = document.getElementById('upload-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPercentage = document.getElementById('progress-percentage');
    const reportPreviewSection = document.getElementById('report-preview-section');
    
    // Evitando erro ao acessar um elemento que pode não existir
    const filesTable = document.getElementById('files-table');
    const filesTableBody = filesTable ? filesTable.getElementsByTagName('tbody')[0] : null;
    
    // Informação do usuário
    fetchUserInfo();
    
    // Eventos para Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        console.log(`Drag and drop detectado - Total de arquivos arrastados: ${files.length}`);
        
        // Lista todos os arquivos arrastados
        for(let i = 0; i < files.length; i++) {
            console.log(`Arquivo arrastado ${i+1}: ${files[i].name}`);
        }
        
        // Para drag and drop, NÃO limpa a lista - permite acumular arquivos
        // selectedFilesList = []; // Removido para permitir acúmulo
        // const filesContainer = document.getElementById('selected-files');
        // filesContainer.innerHTML = ''; // Removido para permitir acúmulo
        
        handleFiles(files);
    }
    
    fileInput.addEventListener('change', function() {
        console.log(`Input change detectado - Total de arquivos selecionados: ${this.files.length}`);
        
        // Lista todos os arquivos selecionados
        for(let i = 0; i < this.files.length; i++) {
            console.log(`Arquivo ${i+1}: ${this.files[i].name}`);
        }
        
        // Limpa a lista apenas se for uma nova seleção (não acumular)
        selectedFilesList = [];
        const filesContainer = document.getElementById('selected-files');
        filesContainer.innerHTML = '';
        
        handleFiles(this.files);
    });
    
    // Gerenciamento dos arquivos selecionados
    let selectedFilesList = [];
    
    function handleFiles(files) {
        console.log(`Processando ${files.length} arquivos selecionados`);
        
        // Filtra apenas arquivos Excel
        console.log(`Lista atual ANTES de processar: ${selectedFilesList.map(f => f.name).join(', ')}`);
        
        Array.from(files).forEach(file => {
            console.log(`Processando arquivo: ${file.name}`);
            if (file.name.match(/\.xlsx|\.xls$/i)) {
                const jaExiste = selectedFilesList.some(f => f.name === file.name);
                console.log(`Arquivo ${file.name} já existe? ${jaExiste}`);
                
                if (!jaExiste) {
                    selectedFilesList.push(file);
                    displayFile(file);
                    console.log(`Arquivo adicionado: ${file.name}`);
                    console.log(`Lista atual APÓS adicionar: ${selectedFilesList.map(f => f.name).join(', ')}`);
                } else {
                    console.log(`Arquivo já existe na lista: ${file.name}`);
                }
            } else {
                console.log(`Arquivo ignorado (não é Excel): ${file.name}`);
            }
        });
        
        console.log(`Total de arquivos na lista: ${selectedFilesList.length}`);
        
        // Habilita o botão de processar se tiver arquivos
        uploadBtn.disabled = selectedFilesList.length === 0;
        
        // Atualiza a interface
        updateFileControls();
    }
    
    function displayFile(file) {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'file-item';
        fileDiv.innerHTML = `
            <span class="file-name">${file.name}</span>
            <button type="button" class="remove-file" data-filename="${file.name}">&times;</button>
        `;
        selectedFiles.appendChild(fileDiv);
        
        // Adiciona evento para remover o arquivo
        fileDiv.querySelector('.remove-file').addEventListener('click', function() {
            const filename = this.getAttribute('data-filename');
            selectedFilesList = selectedFilesList.filter(f => f.name !== filename);
            fileDiv.remove();
            uploadBtn.disabled = selectedFilesList.length === 0;
            updateFileControls();
        });
    }
    
    // Botão para gerar relatório consolidado diretamente
    uploadBtn.addEventListener('click', function() {
        if (selectedFilesList.length === 0) return;
        
        // Prepara e envia os arquivos
        const formData = new FormData();
        selectedFilesList.forEach(file => {
            formData.append('files', file);
        });
        
        // Mostrar barra de progresso
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Processando arquivos...';
        progressPercentage.textContent = '0%';
        
        // Animação simples para a barra de progresso
        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 70) {
                progress += 5;
                progressFill.style.width = progress + '%';
                progressPercentage.textContent = progress + '%';
            }
        }, 200);
        
        // Primeiro processa os arquivos
        fetch('/process_report_files', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao processar arquivos');
            }
            return response.json();
        })
        .then(data => {
            console.log('Arquivos processados com sucesso:', data);
            
            // Atualiza progresso para geração do relatório
            progressFill.style.width = '80%';
            progressText.textContent = 'Gerando relatório consolidado...';
            progressPercentage.textContent = '80%';
            
            // Agora gera o relatório consolidado
            return fetch('/generate_consolidated_report', {
                method: 'POST'
            });
        })
        .then(response => {
            clearInterval(progressInterval);
            
            if (!response.ok) {
                throw new Error('Erro ao gerar o relatório');
            }
            return response.json();
        })
        .then(data => {
            // Completa a barra de progresso
            progressFill.style.width = '100%';
            progressText.textContent = 'Relatório gerado com sucesso!';
            progressPercentage.textContent = '100%';
            
            // Inicia o download automaticamente
            if (data.success) {
                setTimeout(() => {
                    window.location.href = '/download_report';
                    showModal('Sucesso', 'Relatório consolidado gerado e baixado com sucesso!');
                    
                    // Limpa a interface após alguns segundos
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                        progressFill.style.backgroundColor = '#28a745';
                    }, 3000);
                }, 1000);
            }
        })
        .catch(error => {
            clearInterval(progressInterval);
            console.error('Erro:', error);
            
            // Atualiza a barra de progresso para indicar erro
            progressFill.style.width = '100%';
            progressFill.style.backgroundColor = '#f44336';
            progressText.textContent = 'Erro no processamento';
            progressPercentage.textContent = '';
            
            // Mostra mensagem de erro
            showModal('Erro', 'Ocorreu um erro ao processar os arquivos ou gerar o relatório. Verifique se são arquivos Excel válidos gerados pelo PAESTRO.');
        });
    });
    
    // Mostra a seção de geração do relatório
    function updateReportPreview(data) {
        // Atualiza as informações do relatório
        const reportFilesList = document.getElementById('report-files-list');
        
        if (data && data.files && Array.isArray(data.files) && reportFilesList) {
            // Limpa a lista de arquivos existente
            while (reportFilesList.firstChild) {
                reportFilesList.removeChild(reportFilesList.firstChild);
            }
            
            // Adiciona cada arquivo à lista
            data.files.forEach(file => {
                const fileItem = document.createElement('li');
                fileItem.textContent = file.nome || file;
                reportFilesList.appendChild(fileItem);
            });
            
            // Exibe o número total de arquivos
            const fileCountElement = document.getElementById('fileCount');
            if (fileCountElement) {
                fileCountElement.textContent = data.files.length || 0;
            }
        }
        
        // Mostra a seção de prévia do relatório
        if (reportPreviewSection) {
            reportPreviewSection.style.display = 'block';
        }
    }
    
    // Botão para gerar o relatório final
    generateBtn.addEventListener('click', function() {
        fetch('/generate_consolidated_report', {
            method: 'POST'
        })
        .then(response => {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            } else {
                throw new Error('Resposta inesperada do servidor');
            }
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (data.success && data.download_url) {
                // Força o download abrindo diretamente a URL
                window.location.href = data.download_url;
                
                // Mostra mensagem de sucesso
                setTimeout(() => {
                    showModal('Sucesso', 'Relatório consolidado gerado com sucesso! O download foi iniciado.');
                }, 500);
            } else {
                throw new Error('Erro inesperado na resposta do servidor');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            showModal('Erro', error.message || 'Ocorreu um erro ao gerar o relatório consolidado.');
        });
    });
    
    // Função para buscar informações do usuário
    function fetchUserInfo() {
        fetch('/api/get_current_user')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                document.getElementById('username').textContent = data.user.nome || '-';
                document.getElementById('periodo').textContent = data.user.periodo || '-';
            }
        })
        .catch(error => console.error('Erro ao buscar informações do usuário:', error));
    }
    
    // Função para atualizar os controles de arquivos
    function updateFileControls() {
        const fileControls = document.getElementById('file-controls');
        const fileCount = document.getElementById('file-count');
        
        if (selectedFilesList.length > 0) {
            fileControls.style.display = 'block';
            fileCount.textContent = `${selectedFilesList.length} arquivo(s) selecionado(s)`;
        } else {
            fileControls.style.display = 'none';
        }
    }
    
    // Botão para limpar lista de arquivos
    document.getElementById('clear-files-btn').addEventListener('click', function() {
        selectedFilesList = [];
        document.getElementById('selected-files').innerHTML = '';
        uploadBtn.disabled = true;
        updateFileControls();
        console.log('Lista de arquivos limpa');
    });
});