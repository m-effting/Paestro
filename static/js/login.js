document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('login-form');
    const importarBtn = document.getElementById('importar-btn');
    const usernameInput = document.getElementById('username');
    const periodoSelect = document.getElementById('periodo');

    // Função para validar campos e mostrar notificações
    function validateFields() {
        let isValid = true;
        
        if (!usernameInput.value.trim()) {
            alert('Por favor, preencha o nome da dupla');
            usernameInput.focus();
            isValid = false;
        } else if (!periodoSelect.value) {
            alert('Por favor, selecione o período');
            periodoSelect.focus();
            isValid = false;
        }
        
        return isValid;
    }

    // Configura o botão de importar
    importarBtn.addEventListener('click', function(e) {
        if (!validateFields()) {
            return;
        }
        
        // Se validado, faz login e redireciona para importar
        const username = usernameInput.value.trim();
        const periodo = periodoSelect.value;
        
        // Armazena temporariamente durante a sessão
        sessionStorage.setItem('paestro_usuario_temp', username);  
        sessionStorage.setItem('paestro_periodo_temp', periodo);

        
        fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                periodo: periodo
            })
        })
        .then(response => {
            if (!response.ok) throw new Error('Erro no servidor');
            return response.json();
        })
        .then(data => {
            if (data.success) {
                window.location.href = '/importar';
            } else {
                throw new Error(data.error || 'Erro ao fazer login');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert(error.message || 'Erro ao conectar com o servidor');
        });
    });

    // Configura o formulário de login
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!validateFields()) {
            return;
        }
        
        const username = usernameInput.value.trim();
        const periodo = periodoSelect.value;
        
        // Armazena temporariamente durante a sessão
        sessionStorage.setItem('paestro_usuario', username);
        sessionStorage.setItem('paestro_periodo', periodo);
        
        fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                periodo: periodo
            })
        })
        .then(response => {
            if (!response.ok) throw new Error('Erro no servidor');
            return response.json();
        })
        .then(data => {
            if (data.success) {
                window.location.href = '/chamada';
            } else {
                throw new Error(data.error || 'Erro ao fazer login');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert(error.message || 'Erro ao conectar com o servidor');
        });
    });

    // Preenche campos se já existir na sessionStorage (durante a mesma sessão)
    const savedUser = sessionStorage.getItem('paestro_usuario');
    const savedPeriodo = sessionStorage.getItem('paestro_periodo');
    if (savedUser) usernameInput.value = savedUser;
    if (savedPeriodo) periodoSelect.value = savedPeriodo;

    // Limpa o sessionStorage quando a janela/tab for fechada
    window.addEventListener('beforeunload', function() {
        if (!sessionStorage.getItem('isReloading')) {
            sessionStorage.removeItem('paestro_usuario_temp');
            sessionStorage.removeItem('paestro_periodo_temp');
        }
    });

    // Marca recarregamento para não limpar os dados
    window.addEventListener('unload', function() {
        sessionStorage.setItem('isReloading', 'true');
        setTimeout(() => {
            sessionStorage.removeItem('isReloading');
        }, 100);
    });
});