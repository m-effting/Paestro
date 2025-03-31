// Objeto global para armazenamento de dados
const appData = {
    schools: {},
    classes: {},
    attendance_status: {},
    observations: {},
    saved_classes: new Set()
};

// Cache de elementos DOM
const DOM = {
    elements: {},
    init: function() {
        this.elements = {
            escolaSelect: document.getElementById('escola-select'),
            turmaSelect: document.getElementById('turma-select'),
            addAlunoBtn: document.getElementById('add-aluno-btn'),
            alunosTable: document.getElementById('alunos-table').getElementsByTagName('tbody')[0],
            salvarChamadaBtn: document.getElementById('salvar-chamada-btn'),
            exportarChamadaBtn: document.getElementById('exportar-chamada-btn'),
            exportarExcelBtn: document.getElementById('exportar-excel-btn'),
            dataAtualElement: document.getElementById('data-atual'),
            nomeUsuarioElement: document.getElementById('nome-usuario'),
            limparTurmasBtn: document.getElementById('limpar-turmas-btn')
        };
        return this.elements;
    }
};

document.addEventListener('DOMContentLoaded', async function() {
    const {
        escolaSelect,
        turmaSelect,
        addAlunoBtn,
        alunosTable,
        salvarChamadaBtn,
        exportarChamadaBtn,
        dataAtualElement,
        nomeUsuarioElement,
        limparTurmasBtn
    } = DOM.init();

    // Conjunto para armazenar turmas salvas localmente
    let savedClasses = new Set();
    
    // Inicialização da aplicação
    await initApp();

    // Função de inicialização
    async function initApp() {
        await loadSavedClasses();
        updateCurrentDate();
        loadCurrentUser();
        await carregarEscolas();
        
        // Sincroniza as turmas salvas ao iniciar
        await sincronizarTurmasSalvas();
        
        // Carrega a escola selecionada se existir no sessionStorage
        const escolaSalva = sessionStorage.getItem('escola_selecionada');
        if (escolaSalva && escolaSelect.querySelector(`option[value="${escolaSalva}"]`)) {
            escolaSelect.value = escolaSalva;
            await carregarTurmas(escolaSalva);
        }
        
        setupEventListeners();
    }

    // Funções de mensagem
function showError(mensagem) {
    alert('Erro: ' + mensagem);
}

function showSuccess(mensagem) {
    alert('Sucesso: ' + mensagem);
}

// Função para mostrar confirmação (retorna Promise)
function showConfirm(mensagem) {
    return new Promise((resolve) => {
        const confirmed = confirm(mensagem);
        resolve(confirmed);
    });
}

    // Atualiza a data atual
    function updateCurrentDate() {
        const hoje = new Date();
        dataAtualElement.textContent = hoje.toLocaleDateString('pt-BR');
    }

    // Carrega o usuário atual
    function loadCurrentUser() {
        fetch('/api/get_current_user')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const username = data.username || sessionStorage.getItem('paestro_usuario_temp') || '';
                    nomeUsuarioElement.textContent = username;
                }
            })
            .catch(error => {
                console.error('Erro ao obter usuário:', error);
                nomeUsuarioElement.textContent = sessionStorage.getItem('paestro_usuario_temp') || '';
            });
    }

    // Carrega turmas salvas do servidor
    async function loadSavedClasses() {
        try {
            const response = await fetch('/api/get_saved_classes');
            const data = await response.json();
            if (data.success) {
                data.saved_classes.forEach(turma => savedClasses.add(turma));
                atualizarTurmasSalvas();
            }
        } catch (error) {
            console.error('Erro ao carregar turmas salvas:', error);
        }
        
        // Verifica periodicamente por atualizações
        setInterval(async () => {
            try {
                const response = await fetch('/api/get_saved_classes_status');
                const data = await response.json();
                if (data.success) {
                    const novasTurmasSalvas = new Set(data.saved_classes);
                    if (novasTurmasSalvas.size !== savedClasses.size || 
                        ![...novasTurmasSalvas].every(t => savedClasses.has(t))) {
                        savedClasses = novasTurmasSalvas;
                        atualizarTurmasSalvas();
                    }
                }
            } catch (error) {
                console.error('Erro ao verificar turmas salvas:', error);
            }
        }, 5000); // Verifica a cada 5 segundos
    }   

    // Carrega escolas disponíveis
    async function carregarEscolas() {
        try {
            const response = await fetch('/api/get_schools');
            const data = await response.json();
            
            if (data.success) {
                escolaSelect.innerHTML = '<option value="">Selecione uma escola</option>';
                data.schools.forEach(escola => {
                    const option = document.createElement('option');
                    option.value = escola;
                    option.textContent = escola;
                    escolaSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Erro ao carregar escolas:', error);
            showError('Falha ao carregar escolas');
        }
    }

    // Atualiza o visual das turmas salvas
    function atualizarTurmasSalvas() {
        const options = turmaSelect.querySelectorAll('option');
        options.forEach(option => {
            if (option.value) {
                option.classList.toggle('turma-salva', savedClasses.has(option.value));
            }
        });
        
        // Força o redesenho do select (para alguns navegadores que não atualizam imediatamente)
        turmaSelect.style.display = 'none';
        turmaSelect.offsetHeight; // Trigger reflow
        turmaSelect.style.display = '';
    }
    

    // Carrega turmas de uma escola
    async function carregarTurmas(escola) {
        if (!escola) return;
    
        try {
            const response = await fetch('/api/get_school_classes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ school: escola })
            });
            const data = await response.json();
            
            if (data.success) {
                turmaSelect.innerHTML = '<option value="">Selecione uma turma</option>';
                data.classes.forEach(turma => {
                    const option = document.createElement('option');
                    option.value = turma;
                    option.textContent = turma;
                    
                    // Verifica se a turma está salva localmente ou no servidor
                    if (savedClasses.has(turma) || data.saved_classes.includes(turma)) {
                        option.classList.add('turma-salva');
                        savedClasses.add(turma); // Garante sincronização
                    }
                    
                    turmaSelect.appendChild(option);
                });
                
                alunosTable.innerHTML = '';
            }
        } catch (error) {
            console.error('Erro ao carregar turmas:', error);
            showError('Falha ao carregar turmas');
        }
    }
    
    async function sincronizarEstadoCompleto() {
        try {
            const [schoolsRes, savedRes] = await Promise.all([
                fetch('/api/get_schools'),
                fetch('/api/get_saved_classes')
            ]);
            
            const schoolsData = await schoolsRes.json();
            const savedData = await savedRes.json();
            
            if (schoolsData.success && savedData.success) {
                // Atualiza lista de escolas
                escolaSelect.innerHTML = '<option value="">Selecione uma escola</option>';
                schoolsData.schools.forEach(escola => {
                    const option = document.createElement('option');
                    option.value = escola;
                    option.textContent = escola;
                    escolaSelect.appendChild(option);
                });
                
                // Atualiza turmas salvas
                savedClasses = new Set(savedData.saved_classes);
                atualizarTurmasSalvas();
                
                // Restaura seleção anterior se existir
                const escolaSalva = sessionStorage.getItem('escola_selecionada');
                if (escolaSalva && schoolsData.schools.includes(escolaSalva)) {
                    escolaSelect.value = escolaSalva;
                    await carregarTurmas(escolaSalva);
                }
            }
        } catch (error) {
            console.error('Erro ao sincronizar estado:', error);
        }
    }
    

    async function sincronizarTurmasSalvas() {
        try {
            const response = await fetch('/api/get_saved_classes');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            if (data.success) {
                // Cria um novo Set para evitar problemas de referência
                const novasTurmas = new Set(data.saved_classes);
                
                // Verifica se houve mudança antes de atualizar
                if (novasTurmas.size !== savedClasses.size || 
                    ![...novasTurmas].every(t => savedClasses.has(t))) {
                    savedClasses = novasTurmas;
                    atualizarTurmasSalvas();
                }
            } else {
                console.error('Erro ao obter turmas salvas:', data.error);
            }
        } catch (error) {
            console.error('Erro ao sincronizar turmas salvas:', error);
            // Tenta novamente após um curto período
            setTimeout(sincronizarTurmasSalvas, 2000);
        }
    }

    // Carrega alunos de uma turma
    async function carregarAlunos(escola, turma) {
        if (!escola || !turma) return;
    
        try {
            const response = await fetch('/api/get_class', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ school: escola, class: turma })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Se não houver alunos (registros limpos), carrega a lista original
                if (data.alunos.length === 0) {
                    const turmaData = appData.schools[escola][turma];
                    data.alunos = turmaData.map(aluno => ({
                        nome: aluno,
                        presenca: 'P',  // Padrão: presente
                        observacao: ''
                    }));
                }
                
                renderizarAlunos(data.alunos, turma);
            }
        } catch (error) {
            console.error('Erro ao carregar alunos:', error);
            showError('Falha ao carregar alunos');
        }
    }
    

    // Renderiza a lista de alunos na tabela
    function renderizarAlunos(alunos, turma) {
        alunosTable.innerHTML = '';
        
        alunos.forEach(aluno => {
            const row = alunosTable.insertRow();
            
            // Nome do aluno
            const cellNome = row.insertCell(0);
            cellNome.textContent = aluno.nome;
            
            // Botões de presença
            const cellPresenca = row.insertCell(1);
            renderizarBotoesPresenca(cellPresenca, aluno.nome, aluno.presenca, turma);
            
            // Campo de observação
            const cellObs = row.insertCell(2);
            renderizarCampoObservacao(cellObs, aluno.nome, aluno.observacao || '', turma);
        });
    }

    // Renderiza os botões de presença
    function renderizarBotoesPresenca(cell, alunoNome, presencaAtual, turma) {
        const presencaContainer = document.createElement('div');
        presencaContainer.className = 'presenca-buttons';
        presencaContainer.dataset.aluno = alunoNome;

        ['P', 'F', 'FJ'].forEach(opcao => {
            const btn = document.createElement('button');
            btn.className = `presenca-btn ${presencaAtual === opcao ? 'selected-' + opcao : ''}`;
            btn.textContent = opcao;
            btn.dataset.value = opcao;
            
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                atualizarPresenca(presencaContainer, this, alunoNome, turma);
            });
            
            presencaContainer.appendChild(btn);
        });

        cell.appendChild(presencaContainer);
    }

    // Atualiza o status de presença
    function atualizarPresenca(container, botaoClicado, alunoNome, turma) {
        // Remove todas as seleções primeiro
        container.querySelectorAll('.presenca-btn').forEach(b => {
            b.className = 'presenca-btn';
        });
        
        // Adiciona a classe de seleção ao botão clicado
        const opcao = botaoClicado.dataset.value;
        botaoClicado.className = `presenca-btn selected-${opcao}`;
        
        // Atualiza o status no appData
        if (turma) {
            if (!appData.attendance_status[turma]) {
                appData.attendance_status[turma] = {};
            }
            appData.attendance_status[turma][alunoNome] = opcao;
        }
    }

    // Renderiza o campo de observação
    function renderizarCampoObservacao(cell, alunoNome, observacao, turma) {
        const obsInput = document.createElement('input');
        obsInput.type = 'text';
        obsInput.className = 'observacao-input';
        obsInput.dataset.aluno = alunoNome;
        obsInput.value = observacao;
        
        obsInput.addEventListener('change', function() {
            if (turma) {
                if (!appData.observations[turma]) {
                    appData.observations[turma] = {};
                }
                appData.observations[turma][alunoNome] = this.value;
            }
        });
        
        cell.appendChild(obsInput);
    }

    // Adiciona um aluno manualmente
    async function adicionarAluno() {
        const escola = escolaSelect.value;
        const turma = turmaSelect.value;
        
        if (!escola || !turma) {
            showError('Selecione uma escola e turma primeiro');
            return;
        }
        
        const nomeAluno = prompt('Digite o nome do aluno:');
        if (nomeAluno) {
            adicionarAlunoNaTabela(nomeAluno, turma);
            atualizarEstruturasDados(nomeAluno, escola, turma);
        }
    }

    // Adiciona aluno na tabela visual
    function adicionarAlunoNaTabela(nomeAluno, turma) {
        const row = alunosTable.insertRow();
        
        // Nome do aluno
        const cellNome = row.insertCell(0);
        cellNome.textContent = nomeAluno;
        
        // Botões de presença
        const cellPresenca = row.insertCell(1);
        renderizarBotoesPresenca(cellPresenca, nomeAluno, 'P', turma);
        
        // Campo de observação
        const cellObs = row.insertCell(2);
        renderizarCampoObservacao(cellObs, nomeAluno, '', turma);
    }

    // Atualiza estruturas de dados locais
    function atualizarEstruturasDados(nomeAluno, escola, turma) {
        // Adiciona à escola/turma
        if (!appData.schools[escola]) appData.schools[escola] = {};
        if (!appData.schools[escola][turma]) appData.schools[escola][turma] = [];
        appData.schools[escola][turma].push(nomeAluno);
        
        // Inicializa status de presença
        if (!appData.attendance_status[turma]) appData.attendance_status[turma] = {};
        appData.attendance_status[turma][nomeAluno] = 'P';
        
        // Inicializa observações
        if (!appData.observations[turma]) appData.observations[turma] = {};
        appData.observations[turma][nomeAluno] = '';
    }

    // Salva a chamada no servidor
    async function salvarChamada() {
        const escola = escolaSelect.value;
        const turma = turmaSelect.value;
        
        if (!escola || !turma) {
            showError('Selecione uma escola e turma primeiro');
            return;
        }
        
        const alunosData = coletarDadosAlunos();
        
        try {
            const response = await fetch('/api/save_attendance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    escola: escola,
                    turma: turma,
                    alunos: alunosData
                })
            });
            const data = await response.json();
            
            if (data.success) {
                showSuccess('Chamada salva com sucesso!');
                savedClasses.add(turma);
                atualizarTurmasSalvas();
            } else {
                showError(data.error || 'Erro ao salvar chamada');
            }
        } catch (error) {
            console.error('Erro:', error);
            showError('Falha ao comunicar com o servidor');
        }
    }
    
    // Coleta dados dos alunos da tabela
    function coletarDadosAlunos() {
        const alunosData = [];
        const rows = alunosTable.rows;
        
        for (let i = 0; i < rows.length; i++) {
            const cells = rows[i].cells;
            const nome = cells[0].textContent;
            const presencaBtn = cells[1].querySelector('.presenca-btn.selected-P, .presenca-btn.selected-F, .presenca-btn.selected-FJ');
            const presenca = presencaBtn ? presencaBtn.dataset.value : 'P';
            
            alunosData.push({
                nome: nome,
                presenca: presenca,
                observacao: cells[2].querySelector('input').value
            });
        }
        
        return alunosData;
    }


    // Exporta para Excel
    async function exportarParaExcel() {
        const escola = escolaSelect.value;
        if (!escola) {
            showError('Selecione uma escola antes de exportar');
            return;
        }
    
        // Verifica se há turmas salvas
        if (savedClasses.size === 0) {
            showError('Nenhuma chamada foi salva ainda. Por favor, salve pelo menos uma chamada antes de exportar.');
            return;
        }
    
        // Verifica se todas as turmas da escola foram salvas
        const turmasDaEscola = Array.from(turmaSelect.options)
            .map(opt => opt.value)
            .filter(val => val);
    
        const turmasNaoSalvas = turmasDaEscola.filter(t => !savedClasses.has(t));
    
        if (turmasNaoSalvas.length > 0) {
            const confirmacao = await showConfirm(
                `Atenção: Você tem ${turmasNaoSalvas.length} turma(s) não salva(s) nesta escola.\nDeseja continuar?` 
            );
            
            if (!confirmacao) {
                return; // Usuário escolheu não continuar
            }
        }
    
        // Redireciona para a página de exportação 
        window.location.href = `/exportar?escola=${encodeURIComponent(escola)}`;
    }

    // Configura os event listeners
function setupEventListeners() {
    escolaSelect.addEventListener('change', () => {
        sessionStorage.setItem('escola_selecionada', escolaSelect.value);
        carregarTurmas(escolaSelect.value);
    });
    turmaSelect.addEventListener('change', () => carregarAlunos(escolaSelect.value, turmaSelect.value));
    addAlunoBtn.addEventListener('click', adicionarAluno);
    salvarChamadaBtn.addEventListener('click', salvarChamada);
    exportarChamadaBtn.addEventListener('click', exportarParaExcel);
    
    // Verifica turmas salvas quando a página ganha foco
    window.addEventListener('focus', async () => {
        await sincronizarTurmasSalvas();
    });
}

});