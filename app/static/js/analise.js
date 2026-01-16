document.addEventListener('DOMContentLoaded', () => {
    setupDragAndDrop();
    setupEventListeners();
    // Inicializar variáveis globais
    window.results = [];
    window.modal = new Modal();
});

function setupDragAndDrop() {
    const dropArea = document.getElementById('upload-droparea');
    const fileInput = document.getElementById('file-input');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    dropArea.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileInputChange);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
}

function handleFileInputChange() {
    const fileInput = document.getElementById('file-input');
    handleFiles(fileInput.files);
}

function handleFiles(files) {
    const htmlFiles = Array.from(files).filter(file => 
        file.type === 'text/html' || 
        file.name.toLowerCase().endsWith('.html') || 
        file.name.toLowerCase().endsWith('.htm')
    );

    if (htmlFiles.length === 0) {
        showError('Por favor, selecione apenas arquivos HTML.');
        return;
    }

    const selectedFilesContainer = document.getElementById('selected-files');
    selectedFilesContainer.innerHTML = '';

    htmlFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span class="file-name">${file.name}</span>
            <span class="file-size">${formatFileSize(file.size)}</span>
        `;
        selectedFilesContainer.appendChild(fileItem);
    });

    document.getElementById('clear-btn').style.display = 'block';
    updateFileInput(htmlFiles);
}

function updateFileInput(files) {
    const fileInput = document.getElementById('file-input');
    const dataTransfer = new DataTransfer();
    files.forEach(file => dataTransfer.items.add(file));
    fileInput.files = dataTransfer.files;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function clearSelectedFiles() {
    const fileInput = document.getElementById('file-input');
    const selectedFilesContainer = document.getElementById('selected-files');
    fileInput.value = '';
    selectedFilesContainer.innerHTML = '';
    document.getElementById('clear-btn').style.display = 'none';
}

async function handleFormSubmit(event) {
    event.preventDefault();

    const fileInput = document.getElementById('file-input');
    if (fileInput.files.length === 0) {
        showError('Por favor, selecione pelo menos um arquivo HTML.');
        return;
    }

    showProgressBar(true);
    setProgressStatus(0, fileInput.files.length, '');

    try {
        const formData = new FormData();
        const files = Array.from(fileInput.files);
        let totalFiles = files.length;
        let processed = 0;

        updateProgressBar(processed, totalFiles);

        files.forEach(file => {
            formData.append('file', file);
        });

        const xhr = new XMLHttpRequest();
        let uploadStartTime = Date.now();

        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const uploadProgress = (event.loaded / event.total) * 50;
                updateProgressBar(uploadProgress, 100);
                setProgressStatus(processed, totalFiles, 
                    `Enviando arquivos... (${formatBytes(event.loaded)}/${formatBytes(event.total)})`);
            }
        });

        const uploadPromise = new Promise((resolve, reject) => {
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const result = JSON.parse(xhr.responseText);
                            resolve(result);
                        } catch (e) {
                            reject(new Error('Erro ao processar resposta do servidor'));
                        }
                    } else {
                        reject(new Error(`Erro ${xhr.status}: ${xhr.statusText}`));
                    }
                }
            };
            xhr.onerror = function() {
                reject(new Error('Erro de rede durante o envio dos arquivos'));
            };
        });

        xhr.open('POST', '/api/analyze', true);
        xhr.send(formData);

        let processingInterval;
        let currentFileIndex = 0;
        let baseProgress = 50; 
        let progressPerFile = totalFiles > 0 ? 45 / totalFiles : 45; 

        processingInterval = setInterval(() => {
            if (currentFileIndex < totalFiles) {
                baseProgress += progressPerFile / 10; 
                updateProgressBar(baseProgress, 100);

                if (baseProgress >= 50 + (currentFileIndex + 1) * progressPerFile) {
                    currentFileIndex++;
                    processed = currentFileIndex; 
                }

                let statusMessage = '';
                if (baseProgress >= 50 && baseProgress < 70) {
                    statusMessage = 'Analisando estrutura dos arquivos HTML...';
                } else if (baseProgress >= 70 && baseProgress < 85) {
                    statusMessage = 'Extraindo informações de presença e faltas...';
                } else {
                    statusMessage = 'Aplicando regras de classificação...';
                }

                setProgressStatus(processed, totalFiles, statusMessage);
            } else if (baseProgress < 95) {
                baseProgress += 0.5;
                updateProgressBar(baseProgress, 100);
                setProgressStatus(processed, totalFiles, 'Finalizando análise...');
            }
        }, 150);

        const result = await uploadPromise;
        clearInterval(processingInterval);

        if (result.success) {
            updateProgressBar(100, 100);
            setProgressStatus(totalFiles, totalFiles, 'Processamento concluído!');
            await new Promise(resolve => setTimeout(resolve, 1000));
            clearSelectedFiles();

            handleResults(result); 
            
            showProgressBar(false);
        } else {
            showError(`Erro ao processar arquivos: ${result.error}`, result.error_files);
            showProgressBar(false);
        }
    } catch (error) {
        showError(`Erro ao enviar arquivos: ${error.message}`);
        showProgressBar(false);
    }
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function showProgressBar(show) {
    const progressContainer = document.getElementById('progress-container');
    const uploadActions = document.querySelector('.upload-actions');
    progressContainer.style.display = show ? 'block' : 'none';
    uploadActions.style.display = show ? 'none' : 'flex';
}

function updateProgressBar(current, total) {
    const progressFill = document.getElementById('progress-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    const percent = (current / total) * 100;
    progressFill.style.width = `${percent}%`;
    progressPercentage.textContent = `${Math.round(percent)}%`;
}

function setProgressStatus(processed, total, statusText) {
    const currentFile = document.getElementById('current-file');
    const filesProcessed = document.getElementById('files-processed');
    const progressText = document.getElementById('progress-text');
    currentFile.textContent = statusText;
    filesProcessed.textContent = `${processed}/${total} arquivos`;
    if (statusText) {
        progressText.textContent = statusText.split('...')[0];
    }
}

function setLoading(isLoading) {
    const processBtn = document.getElementById('process-btn');
    if (isLoading) {
        processBtn.disabled = true;
        processBtn.innerHTML = '<span class="spinner"></span> Processando...';
    } else {
        processBtn.disabled = false;
        processBtn.innerHTML = 'Processar Arquivos';
    }
}

function showError(message, errorFiles = []) {
    const errorDetails = errorFiles && errorFiles.length > 0 
        ? `<p>Arquivos com erro:</p><ul>${errorFiles.map(file => `<li>${file.name}: ${file.error}</li>`).join('')}</ul>` 
        : '';
    window.modal.alert('Erro', `${message} ${errorDetails}`, 'error');
}

function handleResults(data) {
    // Armazenar resultados originais na variável global
    window.results = data.results || [];

    // Calcular resumo inicial com TODOS os dados
    const summary = calculateCombinedSummary(window.results);
    updateSummary(summary);

    // Configurar filtros (dropdowns)
    setupFilters(window.results);

    // Exibir tabela (inicialmente com todos)
    updateResultTable(window.results);

    document.querySelector('.analysis-results-section').style.display = 'block';
    document.querySelector('.analysis-results-section').scrollIntoView({ behavior: 'smooth' });
}

// ATUALIZADO: Função apenas exibe dados, não calcula
function updateSummary(summary) {
    document.getElementById('total-students').textContent = summary.total_students || 0;
    document.getElementById('total-schools').textContent = summary.total_schools || 0;
    document.getElementById('total-classes').textContent = summary.total_classes || 0;
    document.getElementById('total-absentees').textContent = summary.total_absentees || 0;
    document.getElementById('total-monitors').textContent = summary.total_monitors || 0;
}

// ATUALIZADO: Função calcula estatísticas baseada numa lista (filtrada ou total)
function calculateCombinedSummary(resultsList) {
    if (!resultsList) resultsList = [];

    // Conta alunos faltosos
    const absentees = resultsList.filter(item => {
        const s = String(item.status || item.situacao || '');
        return s.includes('Faltoso');
    });

    // Conta alunos monitorados
    const monitors = resultsList.filter(item => {
        const s = String(item.status || item.situacao || '');
        return s.includes('Monitorar Faltas') || s.includes('Monitorar FJs');
    });

    // Conta escolas e turmas únicas NA LISTA ATUAL
    const schools = new Set(resultsList.map(item => (item.escola || item.unidade || item.school_name || 'Desconhecida').trim()));
    const classes = new Set(resultsList.map(item => (item.turma || item.class_name || 'Desconhecida').trim()));

    return {
        total_students: resultsList.length,
        total_schools: schools.size,
        total_classes: classes.size,
        total_absentees: absentees.length,
        total_monitors: monitors.length
    };
}

function setupFilters(results) {
    const schools = [...new Set(results.map(item => (item.school_name || item.escola || 'N/A').trim()))].sort();
    const schoolFilter = document.getElementById('school-filter');
    schoolFilter.innerHTML = '<option value="todos">Todas</option>';
    schools.forEach(school => {
        schoolFilter.innerHTML += `<option value="${school}">${school}</option>`;
    });

    const classes = [...new Set(results.map(item => (item.class_name || item.turma || 'N/A').trim()))].sort();
    const classFilter = document.getElementById('class-filter');
    classFilter.innerHTML = '<option value="todos">Todas</option>';
    classes.forEach(className => {
        classFilter.innerHTML += `<option value="${className}">${className}</option>`;
    });

    document.getElementById('school-filter').addEventListener('change', applyFilters);
    document.getElementById('class-filter').addEventListener('change', applyFilters);
    document.getElementById('status-filter').addEventListener('change', applyFilters);
    document.getElementById('education-filter').addEventListener('change', applyFilters);
    document.getElementById('toggle-details').addEventListener('change', toggleMonthDetails);
}

function applyFilters() {
    const schoolFilter = document.getElementById('school-filter').value;
    const classFilter = document.getElementById('class-filter').value;
    const statusFilter = document.getElementById('status-filter').value;
    const educationFilter = document.getElementById('education-filter').value;

    let filteredResults = window.results.filter(item => {
        const itemSchool = (item.school_name || item.escola || item.unidade || 'N/A').trim();
        const itemClass = (item.class_name || item.turma || 'N/A').trim();
        
        const schoolMatch = schoolFilter === 'todos' || itemSchool === schoolFilter;
        const classMatch = classFilter === 'todos' || itemClass === classFilter;

        let statusMatch = statusFilter === 'todos';
        if (statusFilter !== 'todos') {
            let itemStatus = [];
            if (Array.isArray(item.status)) itemStatus = item.status;
            else if (Array.isArray(item.situacao)) itemStatus = item.situacao;
            else if (typeof item.status === 'string') itemStatus = item.status.split(',').map(s=>s.trim());
            else if (typeof item.situacao === 'string') itemStatus = item.situacao.split(',').map(s=>s.trim());
            else if (item.classificacao) itemStatus = String(item.classificacao).split(',').map(s=>s.trim());
            else itemStatus = [String(item.status || item.situacao || '')];

            statusMatch = itemStatus.some(s => s.includes(statusFilter));
        }

        let educationMatch = true;
        if (educationFilter !== 'todos') {
            const classNameUpper = itemClass.toUpperCase();
            const isNaoObrigatorio = /GT\s*[0-3]/.test(classNameUpper);
            const isObrigatorio = /GT\s*[4-5]/.test(classNameUpper) || /[1-9][º°]?\s*ANO/.test(classNameUpper);

            if (educationFilter === 'obrigatorio') {
                educationMatch = isObrigatorio;
            } else if (educationFilter === 'nao_obrigatorio') {
                educationMatch = isNaoObrigatorio;
            }
        }

        return schoolMatch && classMatch && statusMatch && educationMatch;
    });

    // ATUALIZADO: Calcula o resumo baseando-se APENAS nos resultados filtrados
    const filteredSummary = calculateCombinedSummary(filteredResults);
    updateSummary(filteredSummary);
    
    // Atualiza a tabela
    updateResultTable(filteredResults);
}

function toggleMonthDetails() {
    const showDetails = document.getElementById('toggle-details').checked;
    const monthColumns = document.querySelectorAll('.monthly-details');
    monthColumns.forEach(col => {
        col.style.display = showDetails ? 'table-cell' : 'none';
    });
}

function updateResultTable(results) {
    const tableBody = document.querySelector('#results-table tbody');
    tableBody.innerHTML = '';

    if (!results || results.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center;">Nenhum resultado encontrado.</td></tr>`;
        return;
    }

    results.forEach(item => {
        const row = document.createElement('tr');
        const schoolName = item.school_name || item.escola || 'N/A';
        const className = item.class_name || item.turma || 'N/A';
        const studentName = item.student_name || item.aluno || 'N/A';
        
        let statusHtml = '';
        if (Array.isArray(item.status)) {
            statusHtml = createStatusBadge(item.status); 
        } else {
            statusHtml = createStatusBadge([item.status || 'Regular']);
        }

        const percPresenca = item.percentual_presenca !== undefined ? item.percentual_presenca : 0;
        const totalF = item.F !== undefined ? item.F : 0;
        const totalFJ = item.FJ !== undefined ? item.FJ : 0;
        const totalP = item.P !== undefined ? item.P : 0;

        let monthlyHtml = '';
        if (item.faltas_por_mes_texto) {
            monthlyHtml = item.faltas_por_mes_texto;
        } else if (item.faltas_por_mes && typeof item.faltas_por_mes === 'object') {
            monthlyHtml = Object.entries(item.faltas_por_mes)
                .filter(([_, count]) => count > 0)
                .map(([month, count]) => {
                    const monthNames = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
                    const monthName = monthNames[parseInt(month)] || month;
                    
                    let styleClass = 'month-absence';
                    const isCompulsory = item.is_compulsory;
                    const limit = isCompulsory ? 10 : 12;
                    
                    if (count >= limit) styleClass += ' high-absence';
                    else if (count >= (limit - 3)) styleClass += ' medium-absence';
                    
                    return `<span class="${styleClass}">${monthName}: ${count}</span>`;
                }).join(' ');
        }
        
        if (!monthlyHtml) monthlyHtml = '-';

        row.innerHTML = `
            <td>${schoolName}</td>
            <td>${className}</td>
            <td>${studentName}</td>
            <td>${statusHtml}</td>
            <td class="numeric">${percPresenca}%</td>
            <td class="numeric">${totalP}</td>
            <td class="numeric">${totalF}</td>
            <td class="numeric">${totalFJ}</td>
            <td class="monthly-details">${monthlyHtml}</td>
        `;

        tableBody.appendChild(row);
    });
    
    toggleMonthDetails();
}

function createStatusBadge(status) {
    let badges = '';
    let statusArray = [];

    if (Array.isArray(status)) {
        statusArray = status;
    } else if (typeof status === 'string') {
        statusArray = status.split(',').map(s => s.trim());
    } else {
        statusArray = [String(status || 'Regular')];
    }

    if (statusArray.some(s => s.includes('Faltoso'))) {
        badges += `<span class="status-badge status-faltoso">Faltoso</span>`;
    }
    if (statusArray.some(s => s.includes('Monitorar Faltas'))) {
        badges += `<span class="status-badge status-monitorar-faltas">Monitorar Faltas</span>`;
    }
    if (statusArray.some(s => s.includes('Monitorar FJ') || s.includes('Monitorar FJs'))) {
        badges += `<span class="status-badge status-monitorar-fjs">Monitorar FJ</span>`;
    }
    if (statusArray.some(s => s.includes('Excesso FJ') || s.includes('Muitas FJs'))) {
        badges += `<span class="status-badge status-muitas-fjs">Excesso FJ</span>`;
    }
    if (badges === '') {
        badges = `<span class="status-badge">Regular</span>`;
    }
    return badges;
}

async function exportData(format = 'excel') {
    setLoading(true);

    try {
        const schoolFilter = document.getElementById('school-filter').value;
        const classFilter = document.getElementById('class-filter').value;
        const statusFilter = document.getElementById('status-filter').value;
        const educationFilter = document.getElementById('education-filter').value;
        const showDetailsCheckbox = document.getElementById('toggle-details');
        const showMonthlyDetails = showDetailsCheckbox ? showDetailsCheckbox.checked : true;

        let dataToExport = window.results || [];
        
        if (schoolFilter !== 'todos' || classFilter !== 'todos' || statusFilter !== 'todos' || educationFilter !== 'todos') {
            dataToExport = dataToExport.filter(item => {
                const schoolMatch = schoolFilter === 'todos' || (item.school_name || item.escola || item.unidade) === schoolFilter;
                const classMatch = classFilter === 'todos' || (item.class_name || item.turma) === classFilter;
                
                let statusMatch = statusFilter === 'todos';
                if (statusFilter !== 'todos') {
                    let sArr = Array.isArray(item.status) ? item.status : String(item.status || '').split(',');
                    statusMatch = sArr.some(s => s.includes(statusFilter));
                }

                let educationMatch = true;
                if (educationFilter !== 'todos') {
                    const className = (item.class_name || item.turma || '').toUpperCase();
                    if (educationFilter === 'obrigatorio') {
                        educationMatch = /GT\s*[4-5]/.test(className) || /[1-9]º/.test(className) || /[1-9] ANO/.test(className);
                    } else if (educationFilter === 'nao_obrigatorio') {
                        educationMatch = /GT\s*[0-3]/.test(className);
                    }
                }
                return schoolMatch && classMatch && statusMatch && educationMatch;
            });
        }

        if (dataToExport.length === 0) {
            window.modal.alert('Aviso', 'Não há dados para exportar com os filtros atuais.', 'warning');
            setLoading(false);
            return;
        }

        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: dataToExport,
                format: format,
                show_monthly_details: showMonthlyDetails
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro ao gerar arquivo');
        }

        const blob = await response.blob();
        if (blob.size === 0) throw new Error('Arquivo gerado está vazio');

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        const disposition = response.headers.get('content-disposition');
        let filename;
        if (disposition && disposition.includes('filename=')) {
            filename = disposition.split('filename=')[1].replace(/"/g, '');
        } else {
            const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            filename = `analise_frequencia_${date}.${format === 'csv' ? 'csv' : 'xlsx'}`;
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        window.modal.alert('Sucesso', `Arquivo exportado com sucesso no formato ${format.toUpperCase()}.`, 'success');
    } catch (error) {
        showError(`Erro ao exportar dados: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

function setupEventListeners() {
    document.getElementById('upload-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('clear-btn').addEventListener('click', clearSelectedFiles);
    document.getElementById('export-excel').addEventListener('click', () => exportData('excel'));

    const toggleDetails = document.getElementById('toggle-details');
    if (toggleDetails) {
        toggleDetails.addEventListener('change', toggleMonthDetails);
    }

    const filters = document.querySelectorAll('.filter-group select');
    filters.forEach(filter => {
        filter.addEventListener('change', applyFilters);
    });

    const tableHeaders = document.querySelectorAll('#results-table th[data-sort]');
    tableHeaders.forEach(th => {
        th.addEventListener('click', () => sortTable(th));
    });

    if (document.getElementById('data-atual')) {
        document.getElementById('data-atual').textContent = new Date().toLocaleDateString('pt-BR');
    }

    if (document.getElementById('nome-usuario')) {
        fetch('/api/get_current_user')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('nome-usuario').textContent = data.username || '';
                    const periodoElement = document.getElementById('periodo-usuario');
                    if (periodoElement) {
                        periodoElement.textContent = data.periodo || '';
                    }
                }
            })
            .catch(error => console.error('Erro ao obter usuário:', error));
    }
}

function sortTable(th) {
    const sortField = th.getAttribute('data-sort');
    const currentDirection = th.classList.contains('sort-asc') ? 'desc' : 'asc';

    document.querySelectorAll('#results-table th').forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
    });

    th.classList.add(`sort-${currentDirection}`);

    const sortedResults = [...window.results].sort((a, b) => {
        const aValue = a[sortField] || 0;
        const bValue = b[sortField] || 0;

        if (!isNaN(aValue) && !isNaN(bValue)) {
            return currentDirection === 'asc' ? aValue - bValue : bValue - aValue;
        }

        if (typeof aValue === 'string' && typeof bValue === 'string') {
            return currentDirection === 'asc' 
                ? aValue.localeCompare(bValue, 'pt-BR') 
                : bValue.localeCompare(aValue, 'pt-BR');
        }
        return 0;
    });

    updateResultTable(sortedResults);
}