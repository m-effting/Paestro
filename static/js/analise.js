document.addEventListener('DOMContentLoaded', () => {
    setupDragAndDrop();
    setupEventListeners();
    // Inicializar variáveis globais
    window.results = [];
    window.modal = new Modal();
    
    // Carregar arquivos salvos
    loadSavedFiles();
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
            // Não precisamos mais chamar handleResults aqui, pois loadSavedFiles já carrega todos os arquivos
            // e chama handleResults com todos os dados combinados
            
            // Limpar a seleção de arquivos
            clearSelectedFiles();
            
            // Atualizar a lista de arquivos salvos e automaticamente carregar todos
            await loadSavedFiles();
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
    const educationFilter = document.getElementById('education-filter').value;
    
    let filteredResults = window.results.filter(item => {
        const schoolMatch = schoolFilter === 'todos' || (item.school_name || item.escola || item.unidade) === schoolFilter;
        const classMatch = classFilter === 'todos' || (item.class_name || item.turma) === classFilter;
        
        // Verificar status - verificar de forma mais robusta
        let statusMatch = statusFilter === 'todos';
        if (statusFilter !== 'todos') {
            // 1. Verifica se status é um array
            if (Array.isArray(item.status)) {
                statusMatch = item.status.includes(statusFilter);
            } 
            // 2. Verifica se situacao é um array
            else if (Array.isArray(item.situacao)) {
                statusMatch = item.situacao.includes(statusFilter);
            } 
            // 3. Verifica se status é uma string
            else if (typeof item.status === 'string') {
                statusMatch = item.status.includes(statusFilter);
            } 
            // 4. Verifica se situacao é uma string
            else if (typeof item.situacao === 'string') {
                statusMatch = item.situacao.includes(statusFilter);
            } 
            // 5. Verifica outras propriedades
            else if (item.classificacao) {
                statusMatch = String(item.classificacao).includes(statusFilter);
            }
            // 6. Caso não encontre, verifica outros formatos (fallback)
            else {
                statusMatch = String(item.status || item.situacao || '').includes(statusFilter);
            }
        }
        
        // Verificar tipo de ensino com base no nome da turma
        let educationMatch = true;
        
        if (educationFilter !== 'todos') {
            const className = (item.class_name || item.turma || '').toUpperCase();
            
            if (educationFilter === 'obrigatorio') {
                // Ensino obrigatório: GT4, GT5 e 1º ao 9º ano
                educationMatch = className.includes('GT4') || 
                                 className.includes('GT5') || 
                                 className.includes('GT 4') || 
                                 className.includes('GT 5') || 
                                 /[1-9]º/.test(className) || 
                                 /[1-9] ANO/.test(className);
            } else if (educationFilter === 'nao_obrigatorio') {
                // Ensino não obrigatório: GT0 a GT3
                educationMatch = className.includes('GT0') || 
                                 className.includes('GT1') || 
                                 className.includes('GT2') || 
                                 className.includes('GT3') || 
                                 className.includes('GT 0') || 
                                 className.includes('GT 1') || 
                                 className.includes('GT 2') || 
                                 className.includes('GT 3');
            }
        }
        
        return schoolMatch && classMatch && statusMatch && educationMatch;
    });
    
    // Atualizar o resumo baseado nos resultados filtrados usando a mesma função que calcula o resumo geral
    const filteredSummary = calculateCombinedSummary(filteredResults);
    
    // Atualizar o resumo e a tabela
    updateSummary(filteredSummary);
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
    
    // Normalizar o status para array para facilitar a lógica
    let statusArray = [];
    
    if (Array.isArray(status)) {
        statusArray = status;
    } else if (typeof status === 'string') {
        statusArray = status.split(',').map(s => s.trim());
    } else {
        statusArray = [String(status || 'Regular')];
    }
    
    // Agora verificamos cada status contra o array normalizado
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
        // Obter os resultados filtrados atuais
        const schoolFilter = document.getElementById('school-filter').value;
        const classFilter = document.getElementById('class-filter').value;
        const statusFilter = document.getElementById('status-filter').value;
        const educationFilter = document.getElementById('education-filter').value;
        
        let dataToExport = window.results || [];
        console.log(`Exportando ${dataToExport.length} registros`);
        
        if (schoolFilter !== 'todos' || classFilter !== 'todos' || statusFilter !== 'todos' || educationFilter !== 'todos') {
            dataToExport = dataToExport.filter(item => {
                const schoolMatch = schoolFilter === 'todos' || (item.school_name || item.escola || item.unidade) === schoolFilter;
                const classMatch = classFilter === 'todos' || (item.class_name || item.turma) === classFilter;
                
                // Verificar status - pode estar como array ou string
                let statusMatch = statusFilter === 'todos';
                if (statusFilter !== 'todos') {
                    if (Array.isArray(item.status)) {
                        statusMatch = item.status.includes(statusFilter);
                    } else if (typeof item.status === 'string') {
                        statusMatch = item.status.includes(statusFilter);
                    } else if (Array.isArray(item.situacao)) {
                        statusMatch = item.situacao.includes(statusFilter);
                    } else if (typeof item.situacao === 'string') {
                        statusMatch = item.situacao.includes(statusFilter);
                    }
                }
                
                // Verificar tipo de ensino com base no nome da turma
                let educationMatch = true;
                
                if (educationFilter !== 'todos') {
                    const className = (item.class_name || item.turma || '').toUpperCase();
                    
                    if (educationFilter === 'obrigatorio') {
                        // Ensino obrigatório: GT4, GT5 e 1º ao 9º ano
                        educationMatch = className.includes('GT4') || 
                                        className.includes('GT5') || 
                                        className.includes('GT 4') || 
                                        className.includes('GT 5') || 
                                        /[1-9]º/.test(className) || 
                                        /[1-9] ANO/.test(className);
                    } else if (educationFilter === 'nao_obrigatorio') {
                        // Ensino não obrigatório: GT0 a GT3
                        educationMatch = className.includes('GT0') || 
                                        className.includes('GT1') || 
                                        className.includes('GT2') || 
                                        className.includes('GT3') || 
                                        className.includes('GT 0') || 
                                        className.includes('GT 1') || 
                                        className.includes('GT 2') || 
                                        className.includes('GT 3');
                    }
                }
                
                return schoolMatch && classMatch && statusMatch && educationMatch;
            });
            console.log(`Após filtros: ${dataToExport.length} registros`);
        }

        if (dataToExport.length === 0) {
            window.modal.alert('Aviso', 'Não há dados para exportar com os filtros atuais.', 'warning');
            setLoading(false);
            return;
        }
        
        // Criar formulário para submissão usando o método POST com tipo aplicação/json
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
        
        // Se a resposta não for ok (status 200-299), lançar erro
        if (!response.ok) {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro ao gerar arquivo');
            } else {
                throw new Error(`Erro no servidor: ${response.status} ${response.statusText}`);
            }
        }
        
        // Criar um blob a partir da resposta
        const blob = await response.blob();
        
        // Verificar se o blob tem conteúdo
        if (blob.size === 0) {
            throw new Error('Arquivo gerado está vazio');
        }
        
        // Criar um link temporário para download
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Obter o nome do arquivo da resposta ou gerar um padrão
        const disposition = response.headers.get('content-disposition');
        let filename;
        if (disposition && disposition.includes('filename=')) {
            filename = disposition.split('filename=')[1].replace(/"/g, '');
        } else {
            const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            filename = `analise_frequencia_${date}.${format === 'csv' ? 'csv' : 'xlsx'}`;
        }
        a.download = filename;
        
        // Adicionar ao documento, clicar e remover
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        // Exibir mensagem de sucesso
        window.modal.alert('Sucesso', `Arquivo exportado com sucesso no formato ${format.toUpperCase()}.`, 'success');
        
    } catch (error) {
        console.error('Erro na exportação:', error);
        showError(`Erro ao exportar dados: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

// As funções toggleLogs, fetchLogs e toggleRules foram removidas
// pois a seção de logs foi removida e a seção de regras agora usa <details>/<summary>

// Funções para gerenciar os arquivos salvos
async function loadSavedFiles() {
    try {
        setLoading(true);
        const response = await fetch('/api/get_analyzed_files');
        const data = await response.json();
        
        if (data.success) {
            const files = data.files || [];
            updateSavedFilesTable(files);
            
            // Carrega automaticamente todos os arquivos, se existirem
            if (files.length > 0) {
                await loadAllAnalyzedFiles(files);
            }
        } else {
            console.error('Erro ao carregar arquivos salvos:', data.error);
        }
    } catch (error) {
        console.error('Erro ao carregar arquivos salvos:', error);
    } finally {
        setLoading(false);
    }
}

// Nova função para carregar todos os arquivos analisados automaticamente
async function loadAllAnalyzedFiles(files) {
    try {
        // Limpa os resultados combinados
        window.combinedResults = [];
        
        // Carrega cada arquivo e adiciona aos resultados
        for (let i = 0; i < files.length; i++) {
            const replaceExisting = (i === 0); // Para o primeiro arquivo, substituir os resultados existentes
            await loadAnalyzedFile(files[i].id, false, replaceExisting);
        }
        
        console.log(`${files.length} arquivos carregados e combinados automaticamente.`);
    } catch (error) {
        console.error(`Erro ao carregar todos os arquivos: ${error.message}`);
        window.modal.alert('Erro', `Erro ao carregar todos os arquivos: ${error.message}`, 'error');
    }
}

function updateSavedFilesTable(files) {
    const tableBody = document.querySelector('#saved-files-table tbody');
    const noFilesMessage = document.getElementById('no-saved-files');
    
    if (files.length === 0) {
        tableBody.innerHTML = '';
        noFilesMessage.style.display = 'block';
        return;
    }
    
    noFilesMessage.style.display = 'none';
    tableBody.innerHTML = '';
        
    files.forEach(file => {
        const row = document.createElement('tr');
        
        // Formatar a data
        const fileDate = new Date(file.date);
        const formattedDate = `${fileDate.toLocaleDateString('pt-BR')} ${fileDate.toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'})}`;
        
        // Obter o nome da escola do arquivo
        let escolaNome = file.school_name || "Desconhecida";
        
        // Assegura que a contagem de alunos está correta
        const studentCount = (file.student_count > 0) ? file.student_count : 
                            (file.results ? file.results.length : 0);
        
        // Obter o nome da turma do arquivo
        let turmaNome = file.class_name || "Desconhecida";
        
        row.innerHTML = `
            <td>
                <input type="checkbox" class="file-checkbox" data-file-id="${file.id}" checked title="Mostrar/ocultar arquivo nos resultados">
            </td>
            <td>${escolaNome} - ${turmaNome}</td>
            <td>${formattedDate}</td>
            <td>${studentCount}</td>
            <td>
                <button class="btn-file-action delete" onclick="deleteAnalyzedFile('${file.id}')" title="Excluir arquivo">
                    <svg viewBox="0 0 24 24" width="18" height="18">
                        <path fill="currentColor" d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z" />
                    </svg>
                </button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Adiciona listeners para os checkboxes
    document.querySelectorAll('.file-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', handleCheckboxChange);
    });
}

// Função para lidar com a alteração nos checkboxes (mostrar/ocultar arquivos nos resultados)
async function handleCheckboxChange(event) {
    const checkbox = event.target;
    const fileId = checkbox.getAttribute('data-file-id');
    const isChecked = checkbox.checked;
    
    // Carregamos todos os arquivos selecionados quando um checkbox é alterado
    const selectedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
    const fileIds = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-file-id'));
    
    if (fileIds.length === 0) {
        // Se nenhum arquivo estiver selecionado, limpa os resultados
        window.combinedResults = [];
        const emptyData = {
            success: true,
            results: [],
            summary: {
                total_students: 0,
                total_schools: 0,
                total_classes: 0,
                total_absentees: 0,
                total_monitors: 0
            }
        };
        handleResults(emptyData);
        return;
    }
    
    setLoading(true);
    
    try {
        // Limpa os resultados combinados
        window.combinedResults = [];
        
        // Carrega cada arquivo selecionado
        for (let i = 0; i < fileIds.length; i++) {
            const replaceExisting = (i === 0); // Para o primeiro arquivo, substituir os resultados existentes
            await loadAnalyzedFile(fileIds[i], false, replaceExisting);
        }
        
        console.log(`${fileIds.length} arquivos selecionados e exibidos nos resultados.`);
    } catch (error) {
        console.error(`Erro ao atualizar resultados: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

// Função combineSelectedFiles foi removida pois todos os arquivos agora são carregados automaticamente

// Array global para armazenar todos os resultados combinados
window.combinedResults = [];

async function loadAnalyzedFile(fileId, showNotifications = true, replaceExisting = true) {
    try {
        setLoading(true);
        
        const response = await fetch(`/api/get_analyzed_file_content/${fileId}`);
        const data = await response.json();
        
        if (data.success) {
            // Se for para substituir os resultados existentes, limpa o array de resultados combinados
            if (replaceExisting) {
                window.combinedResults = [...data.results];
            } else {
                // Adiciona os novos resultados aos existentes
                window.combinedResults = [...window.combinedResults, ...data.results];
            }
            
            // Recalcula o resumo baseado em todos os resultados combinados
            const combinedSummary = calculateCombinedSummary(window.combinedResults);
            
            // Atualiza a estrutura para manter a compatibilidade com o handleResults
            const processedData = {
                success: true,
                results: window.combinedResults,
                summary: combinedSummary
            };
            
            handleResults(processedData);
            
            // Mostrar notificação apenas se solicitado
            if (showNotifications) {
                if (replaceExisting) {
                    window.modal.alert('Sucesso', 'Arquivo carregado com sucesso!');
                } else {
                    window.modal.alert('Sucesso', 'Resultados adicionados com sucesso!');
                }
            }
        } else {
            // Sempre exibe erros, independentemente do valor de showNotifications
            window.modal.alert('Erro', `Erro ao carregar arquivo: ${data.error}`, 'error');
        }
    } catch (error) {
        // Sempre exibe erros, independentemente do valor de showNotifications
        window.modal.alert('Erro', `Erro ao carregar arquivo: ${error.message}`, 'error');
    } finally {
        setLoading(false);
    }
}

// Função para calcular o resumo combinado de múltiplos arquivos
function calculateCombinedSummary(combinedResults) {
    // Adiciona logs para depuração
    console.log('Calculando resumo para', combinedResults.length, 'alunos');
    
    // Conta alunos faltosos
    const absentees = combinedResults.filter(item => {
        // Verificação mais robusta para incluir múltiplos formatos de status
        // 1. Verifica se status é um array
        if (Array.isArray(item.status)) {
            return item.status.includes('Faltoso');
        } 
        // 2. Verifica se situacao é um array
        else if (Array.isArray(item.situacao)) {
            return item.situacao.includes('Faltoso');
        } 
        // 3. Verifica se status é uma string
        else if (typeof item.status === 'string') {
            return item.status.includes('Faltoso');
        } 
        // 4. Verifica se situacao é uma string
        else if (typeof item.situacao === 'string') {
            return item.situacao.includes('Faltoso');
        } 
        // 5. Verifica mais propriedades que podem conter o status
        else if (item.classificacao) {
            const classStr = String(item.classificacao || '');
            return classStr.includes('Faltoso');
        }
        // 6. Último caso: verifica mais um formato (talvez redundante, mas por segurança)
        else {
            const statusStr = String(item.status || item.situacao || '');
            return statusStr.includes('Faltoso');
        }
    });
    
    // Conta alunos monitorados (aqueles que precisam ser monitorados por faltas ou faltas justificadas)
    const monitors = combinedResults.filter(item => {
        // 1. Verifica se status é um array
        if (Array.isArray(item.status)) {
            return item.status.includes('Monitorar Faltas') || item.status.includes('Monitorar FJs');
        } 
        // 2. Verifica se situacao é um array
        else if (Array.isArray(item.situacao)) {
            return item.situacao.includes('Monitorar Faltas') || item.situacao.includes('Monitorar FJs');
        } 
        // 3. Verifica se status é uma string
        else if (typeof item.status === 'string') {
            return item.status.includes('Monitorar Faltas') || item.status.includes('Monitorar FJs');
        } 
        // 4. Verifica se situacao é uma string
        else if (typeof item.situacao === 'string') {
            return item.situacao.includes('Monitorar Faltas') || item.situacao.includes('Monitorar FJs');
        } 
        // 5. Verifica mais propriedades que podem conter o status
        else if (item.classificacao) {
            const classStr = String(item.classificacao || '');
            return classStr.includes('Monitorar Faltas') || classStr.includes('Monitorar FJs');
        }
        // 6. Último caso: verifica como string (talvez redundante, mas por segurança)
        else {
            const statusStr = String(item.status || item.situacao || '');
            return statusStr.includes('Monitorar Faltas') || statusStr.includes('Monitorar FJs');
        }
    });
    
    console.log('Alunos faltosos encontrados:', absentees.length);
    console.log('Alunos monitorados encontrados:', monitors.length);
    
    return {
        total_students: combinedResults.length,
        total_schools: new Set(combinedResults.map(item => item.escola || item.unidade || item.school_name || 'Desconhecida')).size,
        total_classes: new Set(combinedResults.map(item => item.turma || item.class_name || 'Desconhecida')).size,
        total_absentees: absentees.length,
        total_monitors: monitors.length
    };
}

async function deleteAnalyzedFile(fileId) {
    if (!confirm('Tem certeza que deseja excluir este arquivo?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/delete_analyzed_file/${fileId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadSavedFiles();
            window.modal.alert('Sucesso', 'Arquivo excluído com sucesso!');
        } else {
            window.modal.alert('Erro', `Erro ao excluir arquivo: ${data.error}`, 'error');
        }
    } catch (error) {
        window.modal.alert('Erro', `Erro ao excluir arquivo: ${error.message}`, 'error');
    }
}

function setupEventListeners() {
    // Formulário de upload
    document.getElementById('upload-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('clear-btn').addEventListener('click', clearSelectedFiles);
    
    // Botões de ação
    document.getElementById('export-excel').addEventListener('click', () => exportData('excel'));
    
    // Toggle de detalhes mensais
    const toggleDetails = document.getElementById('toggle-details');
    if (toggleDetails) {
        toggleDetails.addEventListener('change', toggleMonthDetails);
    }
    
    // Filtros
    const filters = document.querySelectorAll('.filter-group select');
    filters.forEach(filter => {
        filter.addEventListener('change', applyFilters);
    });
    
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
    
    // Inicializar a função de carregamento de arquivos
    loadSavedFiles();
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
