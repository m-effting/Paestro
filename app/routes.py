import os
import logging
import json
from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app
from werkzeug.utils import secure_filename

from app.services import drive_service, excel_service
from app.logic import analyzer_presenca as analyzer
from app.logic import parser_chamada
from app.logic import reporter
from app.logic import data as data_manager
from datetime import datetime

# Criação do Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.context_processor
def inject_now():
    """Injeta a variável 'now' em todos os templates."""
    return {'now': datetime.now()}

# Configuração de Logger
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. ROTAS DE NAVEGAÇÃO (PÁGINAS)
# ==============================================================================

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/importar')
def importar():
    return render_template('importar.html')

@main_bp.route('/chamada')
def chamada():
    return render_template('chamada.html')

@main_bp.route('/exportar')
def exportar():
    return render_template('exportar.html')

@main_bp.route('/analise')
def analise():
    return render_template('analise.html')

@main_bp.route('/relatorio')
def relatorio():
    return render_template('relatorio.html')

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def get_session_file():
    """
    Retorna o caminho do arquivo de dados COMPARTILHADO.
    Todos os usuários leem/escrevem neste mesmo arquivo JSON.
    """
    filename = "SHARED_VISIT_DATA.json"
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    return os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

# ==============================================================================
# 3. API - LOGIN E USUÁRIO
# ==============================================================================

@main_bp.route('/api/login', methods=['POST'])
def api_login():
    """Registra o usuário atual."""
    data = request.json
    username = data.get('username')
    periodo = data.get('periodo')
    senha = data.get('senha')

    # Validação simples de senha (definida no .env)
    correct_password = os.environ.get('APP_PASSWORD')
    if correct_password and senha != correct_password:
        return jsonify({'success': False, 'error': 'Senha incorreta'}), 401

    # Salva na sessão do navegador
    session['username'] = username
    session['periodo'] = periodo
    
    # Salva também no arquivo compartilhado para aparecer nos relatórios
    app_data = data_manager.load_data(get_session_file())
    app_data['current_user'] = username
    app_data['periodo'] = periodo
    data_manager.save_data(app_data, get_session_file())

    return jsonify({'success': True})

@main_bp.route('/api/get_current_user', methods=['GET'])
def get_current_user():
    """Retorna o usuário logado."""
    # Tenta pegar do arquivo compartilhado primeiro, fallback para sessão
    app_data = data_manager.load_data(get_session_file())
    username = app_data.get('current_user') or session.get('username')
    periodo = app_data.get('periodo') or session.get('periodo')
    
    return jsonify({
        'success': True, 
        'username': username, 
        'periodo': periodo
    })

# ==============================================================================
# 4. API - GERENCIAMENTO DE DADOS (ESCOLAS E TURMAS)
# ==============================================================================

@main_bp.route('/api/get_schools', methods=['GET'])
def get_schools():
    """Retorna lista de escolas carregadas."""
    app_data = data_manager.load_data(get_session_file())
    schools = sorted(list(app_data.get('schools', {}).keys()))
    return jsonify({'success': True, 'schools': schools})

@main_bp.route('/api/get_school_classes', methods=['POST'])
def get_school_classes():
    """Retorna turmas de uma escola específica."""
    req = request.json
    school = req.get('school')
    app_data = data_manager.load_data(get_session_file())
    
    if school and school in app_data['schools']:
        classes = sorted(list(app_data['schools'][school].keys()))
        # Retorna também quais já foram salvas
        saved = app_data.get('saved_classes', {}).get(school, [])
        return jsonify({'success': True, 'classes': classes, 'saved_classes': saved})
    
    return jsonify({'success': False, 'error': 'Escola não encontrada'})

@main_bp.route('/api/get_class', methods=['POST'])
def get_class():
    """Retorna lista de alunos de uma turma."""
    req = request.json
    school = req.get('school')
    turma = req.get('class')
    app_data = data_manager.load_data(get_session_file())

    if school in app_data['schools'] and turma in app_data['schools'][school]:
        lista_alunos = app_data['schools'][school][turma]
        
        # Reconstrói o estado atual (presenças e observações)
        alunos_formatados = []
        for nome in lista_alunos:
            status = app_data.get('attendance_status', {}).get(turma, {}).get(nome, 'P')
            obs = app_data.get('observations', {}).get(turma, {}).get(nome, '')
            alunos_formatados.append({
                'nome': nome,
                'presenca': status,
                'observacao': obs
            })
            
        return jsonify({'success': True, 'alunos': alunos_formatados})
    
    return jsonify({'success': False, 'error': 'Turma não encontrada'})

@main_bp.route('/api/get_saved_classes', methods=['GET'])
def get_saved_classes():
    """Retorna lista de todas as turmas salvas (para os checkmarks)."""
    app_data = data_manager.load_data(get_session_file())
    escola_filtro = request.args.get('escola')
    
    all_saved = []
    saved_dict = app_data.get('saved_classes', {})
    
    if escola_filtro:
        all_saved = saved_dict.get(escola_filtro, [])
    else:
        # Junta todas as listas de todas as escolas
        for lista in saved_dict.values():
            all_saved.extend(lista)
            
    return jsonify({'success': True, 'saved_classes': list(set(all_saved))})

@main_bp.route('/api/get_saved_classes_status', methods=['GET'])
def get_saved_classes_status():
    """Alias para get_saved_classes (usado no polling do JS)."""
    return get_saved_classes()

# ==============================================================================
# 5. API - UPLOAD E IMPORTAÇÃO
# ==============================================================================

@main_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """Recebe arquivos HTML e processa."""
    if 'files[]' not in request.files and 'files' not in request.files:
        # Tenta pegar 'file' único também (usado em alguns JS)
        if 'file' in request.files:
            files = [request.files['file']]
        else:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    else:
        files = request.files.getlist('files[]') or request.files.getlist('files')

    session_file = get_session_file()
    current_data = data_manager.load_data(session_file)
    processed_count = 0
    errors = []

    for file in files:
        if not file or file.filename == '': continue
        try:
            content = file.read().decode('utf-8', errors='ignore')
            
            # Decide qual parser usar (Chamada ou Análise)
            # Se for a página de importar (chamada.js/importar.js), usa parser_chamada
            if 'analise' in request.referrer:
                # Se veio da página de análise, usa o analyzer
                result = analyzer.analyze_attendance_html(content, file.filename)
                # (Lógica de salvar análise seria diferente, mas mantemos simples por enquanto)
            else:
                # Padrão: Parser de Chamada
                result = parser_chamada.parse_chamada(content, file.filename)
                if result and 'schools' in result:
                    data_manager.merge_data(current_data, result)
                    processed_count += 1
                else:
                    errors.append(f"Sem dados válidos em {file.filename}")

        except Exception as e:
            errors.append(f"Erro {file.filename}: {str(e)}")
            logger.error(f"Upload erro: {e}")

    data_manager.save_data(current_data, session_file)
    
    # Retorna estrutura esperada pelo JS
    schools_list = list(current_data.get('schools', {}).keys())
    return jsonify({
        'success': processed_count > 0,
        'processed_count': processed_count,
        'schools': schools_list, 
        'error': "; ".join(errors) if errors else None
    })

@main_bp.route('/api/get_imported_files', methods=['GET'])
def get_imported_files():
    """Retorna lista de arquivos importados (simulado pelas escolas)."""
    app_data = data_manager.load_data(get_session_file())
    files = []
    # Como não salvamos nomes de arquivos, retornamos as escolas como "arquivos"
    for escola in app_data.get('schools', {}):
        files.append({'name': f"Dados de {escola}"})
    return jsonify({'success': True, 'files': files})

@main_bp.route('/api/delete_file', methods=['POST'])
def delete_file():
    """Apaga dados de uma escola (simulando apagar arquivo)."""
    filename = request.json.get('filename', '')
    escola_nome = filename.replace("Dados de ", "")
    
    app_data = data_manager.load_data(get_session_file())
    if escola_nome in app_data.get('schools', {}):
        del app_data['schools'][escola_nome]
        # Remove também das turmas salvas
        if escola_nome in app_data.get('saved_classes', {}):
            del app_data['saved_classes'][escola_nome]
        
        data_manager.save_data(app_data, get_session_file())
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Arquivo não encontrado'})

# ==============================================================================
# 6. API - SALVAR E ANOTAÇÕES
# ==============================================================================

@main_bp.route('/api/save_attendance', methods=['POST'])
def save_attendance():
    """Salva a chamada e marca turma como concluída."""
    try:
        req = request.json
        escola = req.get('escola')
        turma = req.get('turma')
        alunos_lista = req.get('alunos', []) # [{nome, presenca, observacao}]

        app_data = data_manager.load_data(get_session_file())

        # Inicializa estruturas
        if 'attendance_status' not in app_data: app_data['attendance_status'] = {}
        if 'observations' not in app_data: app_data['observations'] = {}
        if turma not in app_data['attendance_status']: app_data['attendance_status'][turma] = {}
        if turma not in app_data['observations']: app_data['observations'][turma] = {}

        # Salva dados dos alunos
        for aluno in alunos_lista:
            nome = aluno.get('nome')
            app_data['attendance_status'][turma][nome] = aluno.get('presenca')
            app_data['observations'][turma][nome] = aluno.get('observacao')

        # Marca turma como salva
        if 'saved_classes' not in app_data: app_data['saved_classes'] = {}
        if escola not in app_data['saved_classes']: app_data['saved_classes'][escola] = []
        
        if turma not in app_data['saved_classes'][escola]:
            app_data['saved_classes'][escola].append(turma)

        data_manager.save_data(app_data, get_session_file())
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Erro save_attendance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/get_annotations', methods=['GET'])
def get_annotations():
    escola = request.args.get('escola')
    app_data = data_manager.load_data(get_session_file())
    notes = app_data.get('unit_annotations', {}).get(escola, [])
    return jsonify({'success': True, 'annotations': notes})

@main_bp.route('/api/add_annotation', methods=['POST'])
def add_annotation():
    req = request.json
    escola = req.get('escola')
    nota = req.get('anotacao')
    
    app_data = data_manager.load_data(get_session_file())
    if 'unit_annotations' not in app_data: app_data['unit_annotations'] = {}
    if escola not in app_data['unit_annotations']: app_data['unit_annotations'][escola] = []
    
    app_data['unit_annotations'][escola].append(nota)
    data_manager.save_data(app_data, get_session_file())
    return jsonify({'success': True})

@main_bp.route('/api/delete_annotation', methods=['POST'])
def delete_annotation():
    req = request.json
    escola = req.get('escola')
    nota = req.get('anotacao')
    
    app_data = data_manager.load_data(get_session_file())
    if escola in app_data.get('unit_annotations', {}):
        if nota in app_data['unit_annotations'][escola]:
            app_data['unit_annotations'][escola].remove(nota)
            data_manager.save_data(app_data, get_session_file())
    return jsonify({'success': True})

# ==============================================================================
# FUNÇÃO AUXILIAR DE LIMPEZA
# ==============================================================================

def limpar_dados_escola(app_data, escola):
    """
    Remove TODOS os dados de uma escola específica:
    - Marcação de turmas salvas
    - Status de presença dos alunos (F, P, FJ)
    - Observações lançadas
    """
    # 1. Remove das turmas salvas (o check visual)
    if escola in app_data.get('saved_classes', {}):
        del app_data['saved_classes'][escola]
    
    # 2. Remove status de presença (dados reais)
    # attendance_status é { 'Turma A': { 'Aluno 1': 'P' } }
    # Precisamos iterar para achar as turmas dessa escola
    turmas_da_escola = list(app_data.get('schools', {}).get(escola, {}).keys())
    
    for turma in turmas_da_escola:
        # Remove presenças
        if turma in app_data.get('attendance_status', {}):
            del app_data['attendance_status'][turma]
        
        # Remove observações
        if turma in app_data.get('observations', {}):
            del app_data['observations'][turma]

    logger.info(f"Dados da escola {escola} foram totalmente limpos.")
    return app_data

# ==============================================================================
# 7. API - EXPORTAÇÃO (DRIVE E DOWNLOAD)
# ==============================================================================

@main_bp.route('/api/get_drive_folders', methods=['GET'])
def get_drive_folders_route():
    """Retorna a lista de escolas configuradas no Drive."""
    # Chama a função do arquivo drive_service.py
    return drive_service.get_drive_folders()

@main_bp.route('/api/export_excel_drive', methods=['POST'])
def export_excel_drive():
    """
    Gera o Excel, faz upload para o Google Drive e LIMPA os dados salvos após o sucesso.
    """
    try:
        # 1. Carrega dados da requisição e da sessão
        req_data = request.json
        escola = req_data.get('escola')
        folder_id = req_data.get('folder_id')
        auto_clear = req_data.get('auto_clear') # Vem como True do Javascript
        
        session_file = get_session_file()
        app_data = data_manager.load_data(session_file)

        # 2. Prepara os dados para o Excel (Igual ao download manual)
        turmas_salvas = app_data.get('saved_classes', {}).get(escola, [])
        
        if not turmas_salvas:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportar'}), 400

        classes_exp = {}
        status_exp = {}
        obs_exp = {}
        
        for turma in turmas_salvas:
            # Garante que a turma existe nos dados da escola
            if turma in app_data['schools'].get(escola, {}):
                classes_exp[turma] = app_data['schools'][escola][turma]
                status_exp[turma] = app_data['attendance_status'].get(turma, {})
                obs_exp[turma] = app_data['observations'].get(turma, {})

        # 3. Gera o arquivo Excel em memória usando o excel_service
        excel_buffer = excel_service.export_to_excel(
            classes_exp, status_exp, obs_exp, 
            None, 
            app_data.get('current_user'), 
            app_data.get('periodo'), 
            escola
        )
        
        # Define o nome do arquivo
        filename = excel_service.get_excel_filename(
            escola, 
            app_data.get('periodo'), 
            app_data.get('current_user')
        )

        # 4. Faz o Upload para o Drive
        # Pega os bytes do arquivo gerado
        excel_bytes = excel_buffer.getvalue()
        
        file_id = drive_service.upload_excel_to_drive(excel_bytes, filename, folder_id)
        
        if not file_id:
            return jsonify({'success': False, 'error': 'Falha ao fazer upload para o Drive (Verifique permissões)'}), 500

        # 5. limpeza dos dados (Auto-Clear)

        if auto_clear:
            app_data = limpar_dados_escola(app_data, escola) # <--- CHAMA A NOVA FUNÇÃO
            data_manager.save_data(app_data, session_file)

        return jsonify({'success': True, 'drive_file_id': file_id})

    except Exception as e:
        logger.error(f"Erro export drive: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/export_excel', methods=['GET'])
def export_excel_download():
    """
    Baixa o Excel diretamente e LIMPA TUDO (Deep Clean) se solicitado.
    """
    try:
        # 1. Captura parâmetros
        escola = request.args.get('escola')
        auto_clear = request.args.get('auto_clear') == 'true'
        
        session_file = get_session_file()
        app_data = data_manager.load_data(session_file)
        
        # 2. Validação: Verifica se há algo para exportar
        turmas_salvas = app_data.get('saved_classes', {}).get(escola, [])
        if not turmas_salvas:
            return "Nenhuma turma salva para exportar nesta escola.", 400

        # 3. Prepara os dados para o Excel
        classes_exp = {}
        status_exp = {}
        obs_exp = {}
        
        for turma in turmas_salvas:
            # Garante que a turma existe na estrutura da escola
            if turma in app_data['schools'].get(escola, {}):
                classes_exp[turma] = app_data['schools'][escola][turma]
                status_exp[turma] = app_data['attendance_status'].get(turma, {})
                obs_exp[turma] = app_data['observations'].get(turma, {})

        # 4. Gera o arquivo Excel em memória
        excel_file = excel_service.export_to_excel(
            classes_exp, status_exp, obs_exp, 
            None, 
            app_data.get('current_user'), 
            app_data.get('periodo'), 
            escola
        )

        filename = excel_service.get_excel_filename(
            escola, 
            app_data.get('periodo'), 
            app_data.get('current_user')
        )

        # 5. LIMPEZA COMPLETA (Deep Clean) ANTES DE ENVIAR
        # Importante fazer isso antes do return, pois o return encerra a função
        if auto_clear:
            app_data = limpar_dados_escola(app_data, escola) # Chama a função auxiliar
            data_manager.save_data(app_data, session_file)

        # 6. Envia o arquivo para o navegador
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Erro download excel: {e}")
        return str(e), 500

# ==============================================================================
# 8. API - MÓDULO DE ANÁLISE (JS analise.js)
# ==============================================================================

@main_bp.route('/api/analyze', methods=['POST'])
def api_analyze():
    # Rota usada pelo analise.js para upload
    # Reutiliza a lógica de upload mas focada no analyzer
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file'}), 400
    
    file = request.files['file']
    content = file.read().decode('utf-8', errors='ignore')
    
    result = analyzer.analyze_attendance_html(content, file.filename)
    
    # Se precisar salvar resultados da análise...
    # Por enquanto retorna direto para o JS mostrar na tela
    if result:
        # Aplica regras
        final_data = analyzer.apply_classification_rules(result)
        return jsonify({'success': True, 'results': final_data, 'summary': {}})
    else:
        return jsonify({'success': False, 'error': 'Falha na análise'})