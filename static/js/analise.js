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
    
    // Prevenir comportamento padrão do navegador
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    // Destacar a área quando o arquivo é arrastado sobre ela
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    // Remover destaque quando o arquivo sai da área
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    // Lidar com o arquivo quando ele é solto
    dropArea.addEventListener('drop', handleDrop, false);
    
    // Lidar com arquivos selecionados pelo input
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
    // Limitar a apenas arquivos HTML/HTM
    const htmlFiles = Array.from(files).filter(file => 
        file.type === 'text/html' || 
        file.name.toLowerCase().endsWith('.html') || 
        file.name.toLowerCase().endsWith('.htm')
    );
    
    if (htmlFiles.length === 0) {
        showError('Por favor, selecione apenas arquivos HTML.');
        return;
    }
    
    // Exibir os arquivos selecionados
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
    
    // Mostrar botão de limpar
    document.getElementById('clear-btn').style.display = 'block';
    
    // Atualizar o input de arquivo para conter apenas os arquivos HTML
    updateFileInput(htmlFiles);
}

function updateFileInput(files) {
    const fileInput = document.getElementById('file-input');
    const dataTransfer = new DataTransfer();
    
    files.forEach(file => {
        dataTransfer.items.add(file);
    });
    
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
    
    setLoading(true);
    
    try {
        const formData = new FormData();
        Array.from(fileInput.files).forEach(file => {
            formData.append('file', file);
        });
        
        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            handleResults(result);
        } else {
            showError(`Erro ao processar arquivos: ${result.error}`, result.error_files);
        }
    } catch (error) {
        showError(`Erro ao enviar arquivos: ${error.message}`);
    } finally {
        setLoading(false);
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
    // Armazenar resultados na variável global
    window.results = data.results || [];
    
    // Atualizar o resumo
    updateSummary(data.summary || {});
    
    // Configurar filtros
    setupFilters(window.results);
    
    // Exibir resultados na tabela
    updateResultTable(window.results);
    
    // Mostrar a seção de resultados
    document.querySelector('.analysis-results-section').style.display = 'block';
    
    // Rolar para a seção de resultados
    document.querySelector('.analysis-results-section').scrollIntoView({ behavior: 'smooth' });
}

function updateSummary(summary) {
    document.getElementById('total-students').textContent = summary.total_students || 0;
    document.getElementById('total-schools').textContent = summary.total_schools || 0;
    document.getElementById('total-classes').textContent = summary.total_classes || 0;
    document.getElementById('total-absentees').textContent = summary.total_absentees || 0;
    
    // Somar todos os alunos com status "Monitorar Faltas" e "Monitorar FJs"
    let totalMonitored = 0;
    if (window.results && window.results.length > 0) {
        totalMonitored = window.results.filter(item => 
            (item.status && (item.status.includes('Monitorar Faltas') || item.status.includes('Monitorar FJs')))
        ).length;
    } else {
        totalMonitored = summary.total_monitors || 0;
    }
    
    document.getElementById('total-monitors').textContent = totalMonitored;
}

function setupFilters(results) {
    // Extrair escolas únicas
    const schools = [...new Set(results.map(item => item.school_name || item.escola))];
    const schoolFilter = document.getElementById('school-filter');
    schoolFilter.innerHTML = '<option value="todos">Todas</option>';
    schools.forEach(school => {
        schoolFilter.innerHTML += `<option value="${school}">${school}</option>`;
    });
    
    // Extrair turmas únicas
    const classes = [...new Set(results.map(item => item.class_name || item.turma))];
    const classFilter = document.getElementById('class-filter');
    classFilter.innerHTML = '<option value="todos">Todas</option>';
    classes.forEach(className => {
        classFilter.innerHTML += `<option value="${className}">${className}</option>`;
    });
    
    // Adicionar ouvintes de eventos aos filtros
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
    // Removemos o filtro de tipo de ensino
    // const educationFilter = document.getElementById('education-filter').value;
    
    let filteredResults = window.results.filter(item => {
        const schoolMatch = schoolFilter === 'todos' || (item.school_name || item.escola) === schoolFilter;
        const classMatch = classFilter === 'todos' || (item.class_name || item.turma) === classFilter;
        const statusMatch = statusFilter === 'todos' || (item.status && item.status.includes(statusFilter));
        // Removemos a verificação de tipo de ensino
        const educationMatch = true;
        
        return schoolMatch && classMatch && statusMatch && educationMatch;
    });
    
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
    
    if (results.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="11" style="text-align: center;">Nenhum resultado encontrado com os filtros atuais.</td></tr>`;
        return;
    }
    
    results.forEach(item => {
        const row = document.createElement('tr');
        
        // Normalizar nomes de campos para compatibilidade
        const schoolName = item.school_name || item.escola || item.unidade || 'N/A';
        const className = item.class_name || item.turma || 'N/A';
        const educationType = item.education_type || item.tipo_ensino || 'N/A';
        const studentName = item.student_name || item.aluno || 'N/A';
        const status = item.status || 'Regular';
        const classification = item.classification || item.classificacao || 'N/A';
        const attendancePercentage = item.attendance_percentage || item.percentual_presenca || 0;
        const absenceTotal = item.F || item.absence_total || item.total_faltas || 0;
        const justifiedTotal = item.FJ || item.justified_total || item.total_fj || 0;
        const presenceTotal = item.P || item.presence_total || item.total_presencas || 0;
        
        // Obter dados de faltas por mês (prioridade: faltas_por_mes > faltas_por_mes_texto > monthly_absences)
        let monthlyAbsences = {};
        
        // Se temos o objeto de faltas por mês estruturado, usar ele
        if (item.faltas_por_mes && typeof item.faltas_por_mes === 'object') {
            monthlyAbsences = item.faltas_por_mes;
        }
        // Se temos a string formatada, fazer o parsing
        else if (item.faltas_por_mes_texto && typeof item.faltas_por_mes_texto === 'string') {
            const faltasTexto = item.faltas_por_mes_texto;
            faltasTexto.split(',').forEach(par => {
                const [mes, faltas] = par.trim().split(':');
                if (mes && faltas) {
                    monthlyAbsences[mes.trim()] = parseInt(faltas.trim(), 10) || 0;
                }
            });
        }
        // Fallback para monthly_absences
        else if (item.monthly_absences && typeof item.monthly_absences === 'object') {
            monthlyAbsences = item.monthly_absences;
        }
        
        // Construir a célula para as faltas mensais
        const monthlyAbsencesCell = Object.entries(monthlyAbsences)
            .map(([month, count]) => {
                // Determinar o limite de faltas com base no tipo de educação
                let limiteMonitoria, limiteFaltoso;
                
                if (educationType === 'fundamental' || educationType === 'infantil_obrigatorio') {
                    limiteMonitoria = 7;
                    limiteFaltoso = 10;
                } else {
                    limiteMonitoria = 10;
                    limiteFaltoso = 13;
                }
                
                // Aplicar classe CSS com base no número de faltas
                let cssClass = 'month-absence';
                if (count >= limiteFaltoso) {
                    cssClass = 'month-absence high-absence';
                } else if (count >= limiteMonitoria) {
                    cssClass = 'month-absence medium-absence';
                }
                
                return `<span class="${cssClass}">${month}: ${count}</span>`;
            })
            .join(' ');
        
        row.innerHTML = `
            <td>${schoolName}</td>
            <td>${className}</td>
            <td>${studentName}</td>
            <td>${createStatusBadge(status)}</td>
            <td class="numeric">${attendancePercentage}%</td>
            <td class="numeric">${presenceTotal}</td>
            <td class="numeric">${absenceTotal}</td>
            <td class="numeric">${justifiedTotal}</td>
            <td class="monthly-details">${monthlyAbsencesCell || 'N/A'}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

function createStatusBadge(status) {
    let badges = '';
    
    if (status.includes('Faltoso')) {
        badges += `<span class="status-badge status-faltoso">Faltoso</span>`;
    }
    
    if (status.includes('Monitorar Faltas')) {
        badges += `<span class="status-badge status-monitorar-faltas">Monitorar Faltas</span>`;
    }
    
    if (status.includes('Monitorar FJ') || status.includes('Monitorar FJs')) {
        badges += `<span class="status-badge status-monitorar-fjs">Monitorar FJ</span>`;
    }
    
    if (status.includes('Excesso FJ') || status.includes('Muitas FJs')) {
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
        // Obter os resultados filtrados atuais
        const schoolFilter = document.getElementById('school-filter').value;
        const classFilter = document.getElementById('class-filter').value;
        const statusFilter = document.getElementById('status-filter').value;
        const educationFilter = document.getElementById('education-filter').value;
        
        let dataToExport = window.results;
        if (schoolFilter !== 'todos' || classFilter !== 'todos' || statusFilter !== 'todos' || educationFilter !== 'todos') {
            dataToExport = window.results.filter(item => {
                const schoolMatch = schoolFilter === 'todos' || (item.school_name || item.escola || item.unidade) === schoolFilter;
                const classMatch = classFilter === 'todos' || (item.class_name || item.turma) === classFilter;
                const statusMatch = statusFilter === 'todos' || (item.status && item.status.includes(statusFilter));
                // Removemos a verificação de tipo de ensino
                const educationMatch = true;
                
                return schoolMatch && classMatch && statusMatch && educationMatch;
            });
        }
        
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data: dataToExport,
                format: format
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro ao gerar arquivo');
        }
        
        // Criar um blob a partir da resposta
        const blob = await response.blob();
        
        // Criar um link temporário para download
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Definir o nome do arquivo
        const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        a.download = `analise_frequencia_${date}.xlsx`;
        
        // Adicionar ao documento, clicar e remover
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        // Exibir mensagem de sucesso
        window.modal.alert('Sucesso', `Arquivo exportado com sucesso no formato ${format.toUpperCase()}.`, 'success');
        
    } catch (error) {
        showError(`Erro ao exportar dados: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

// As funções toggleLogs, fetchLogs e toggleRules foram removidas
// pois a seção de logs foi removida e a seção de regras agora usa <details>/<summary>

function setupEventListeners() {
    // Formulário de upload
    document.getElementById('upload-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('clear-btn').addEventListener('click', clearSelectedFiles);
    
    // Botões de ação
    document.getElementById('export-excel').addEventListener('click', () => exportData('excel'));
    
    // Ordenação da tabela
    const tableHeaders = document.querySelectorAll('#results-table th[data-sort]');
    tableHeaders.forEach(th => {
        th.addEventListener('click', () => sortTable(th));
    });
    
    // Atualizar data atual
    if (document.getElementById('data-atual')) {
        document.getElementById('data-atual').textContent = new Date().toLocaleDateString('pt-BR');
    }
    
    // Atualizar nome do usuário
    if (document.getElementById('nome-usuario')) {
        fetch('/api/get_current_user')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.username) {
                    document.getElementById('nome-usuario').textContent = data.username;
                }
            })
            .catch(error => console.error('Erro ao obter usuário:', error));
    }
}

function sortTable(th) {
    const sortField = th.getAttribute('data-sort');
    const currentDirection = th.classList.contains('sort-asc') ? 'desc' : 'asc';
    
    // Remover classes de ordenação de todos os cabeçalhos
    document.querySelectorAll('#results-table th').forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
    });
    
    // Aplicar classe de ordenação ao cabeçalho clicado
    th.classList.add(`sort-${currentDirection}`);
    
    // Ordenar os resultados
    const sortedResults = [...window.results].sort((a, b) => {
        const aValue = a[sortField] || 0;
        const bValue = b[sortField] || 0;
        
        // Verificar se está ordenando campos numéricos
        if (!isNaN(aValue) && !isNaN(bValue)) {
            return currentDirection === 'asc' ? aValue - bValue : bValue - aValue;
        }
        
        // Ordenar campos de texto
        if (typeof aValue === 'string' && typeof bValue === 'string') {
            return currentDirection === 'asc' 
                ? aValue.localeCompare(bValue, 'pt-BR') 
                : bValue.localeCompare(aValue, 'pt-BR');
        }
        
        return 0;
    });
    
    // Atualizar a tabela com os resultados ordenados
    updateResultTable(sortedResults);
}
