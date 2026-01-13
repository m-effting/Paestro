import os
import logging
import unicodedata
import re
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app
from werkzeug.utils import secure_filename

from app.services import drive_service, excel_service
from app.logic import analyzer_presenca as analyzer
from app.logic import parser_chamada
from app.logic import reporter
from app.logic import data as data_manager

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
def index(): return render_template('index.html')

@main_bp.route('/importar')
def importar(): return render_template('importar.html')

@main_bp.route('/chamada')
def chamada(): return render_template('chamada.html')

@main_bp.route('/exportar')
def exportar(): return render_template('exportar.html')

@main_bp.route('/analise')
def analise(): return render_template('analise.html')

@main_bp.route('/relatorio')
def relatorio(): return render_template('relatorio.html')

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def get_session_file():
    filename = "SHARED_VISIT_DATA.json"
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    return os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

def limpar_dados_escola(app_data, escola):
    """Deep Clean: Remove tudo de uma escola específica."""
    if escola in app_data.get('saved_classes', {}):
        del app_data['saved_classes'][escola]
    
    if 'unit_annotations' in app_data and escola in app_data['unit_annotations']:
        del app_data['unit_annotations'][escola]
    
    turmas_da_escola = list(app_data.get('schools', {}).get(escola, {}).keys())
    for turma in turmas_da_escola:
        if turma in app_data.get('attendance_status', {}):
            del app_data['attendance_status'][turma]
        if turma in app_data.get('observations', {}):
            del app_data['observations'][turma]

    logger.info(f"Dados da escola {escola} foram totalmente limpos.")
    return app_data

# ==============================================================================
# 3. API - LOGIN E USUÁRIO
# ==============================================================================

@main_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    periodo = data.get('periodo')
    senha = data.get('senha')

    correct_password = os.environ.get('APP_PASSWORD')
    if correct_password and senha != correct_password:
        return jsonify({'success': False, 'error': 'Senha incorreta'}), 401

    session['username'] = username
    session['periodo'] = periodo
    
    app_data = data_manager.load_data(get_session_file())
    app_data['current_user'] = username
    app_data['periodo'] = periodo
    data_manager.save_data(app_data, get_session_file())

    return jsonify({'success': True})

@main_bp.route('/api/get_current_user', methods=['GET'])
def get_current_user():
    app_data = data_manager.load_data(get_session_file())
    username = app_data.get('current_user') or session.get('username')
    periodo = app_data.get('periodo') or session.get('periodo')
    return jsonify({'success': True, 'username': username, 'periodo': periodo})

# ==============================================================================
# 4. API - GERENCIAMENTO DE DADOS (ESCOLAS E TURMAS)
# ==============================================================================

@main_bp.route('/api/get_schools', methods=['GET'])
def get_schools():
    app_data = data_manager.load_data(get_session_file())
    schools = sorted(list(app_data.get('schools', {}).keys()))
    return jsonify({'success': True, 'schools': schools})

@main_bp.route('/api/get_school_classes', methods=['POST'])
def get_school_classes():
    req = request.json
    school = req.get('school')
    app_data = data_manager.load_data(get_session_file())
    
    if school and school in app_data['schools']:
        classes = sorted(list(app_data['schools'][school].keys()))
        saved = app_data.get('saved_classes', {}).get(school, [])
        return jsonify({'success': True, 'classes': classes, 'saved_classes': saved})
    
    return jsonify({'success': False, 'error': 'Escola não encontrada'})

@main_bp.route('/api/get_class', methods=['POST'])
def get_class():
    req = request.json
    school = req.get('school')
    turma = req.get('class')
    app_data = data_manager.load_data(get_session_file())

    if school in app_data['schools'] and turma in app_data['schools'][school]:
        lista_alunos = app_data['schools'][school][turma]
        alunos_formatados = []
        for nome in lista_alunos:
            status = app_data.get('attendance_status', {}).get(turma, {}).get(nome, 'P')
            obs = app_data.get('observations', {}).get(turma, {}).get(nome, '')
            alunos_formatados.append({'nome': nome, 'presenca': status, 'observacao': obs})
        return jsonify({'success': True, 'alunos': alunos_formatados})
    
    return jsonify({'success': False, 'error': 'Turma não encontrada'})

@main_bp.route('/api/get_saved_classes', methods=['GET'])
def get_saved_classes():
    app_data = data_manager.load_data(get_session_file())
    escola_filtro = request.args.get('escola')
    all_saved = []
    saved_dict = app_data.get('saved_classes', {})
    
    if escola_filtro:
        all_saved = saved_dict.get(escola_filtro, [])
    else:
        for lista in saved_dict.values():
            all_saved.extend(lista)
            
    return jsonify({'success': True, 'saved_classes': list(set(all_saved))})

@main_bp.route('/api/get_saved_classes_status', methods=['GET'])
def get_saved_classes_status():
    return get_saved_classes()

# ==============================================================================
# 5. API - UPLOAD E IMPORTAÇÃO (CHAMADA PRESENCIAL)
# ==============================================================================

@main_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload para a tela de Importar/Chamada."""
    if 'files[]' not in request.files and 'files' not in request.files:
        if 'file' in request.files: files = [request.files['file']]
        else: return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
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
            
            # Se veio da página de análise (referrer check simples)
            if 'analise' in request.referrer:
                result = analyzer.analyze_attendance_html(content, file.filename)
                # Nota: Lógica de salvar análise é tratada em /api/analyze, aqui é só fallback
            else:
                # Padrão: Parser de Chamada Presencial
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
    schools_list = list(current_data.get('schools', {}).keys())
    return jsonify({
        'success': processed_count > 0,
        'processed_count': processed_count,
        'schools': schools_list, 
        'error': "; ".join(errors) if errors else None
    })

@main_bp.route('/api/get_imported_files', methods=['GET'])
def get_imported_files():
    app_data = data_manager.load_data(get_session_file())
    files = []
    for escola in app_data.get('schools', {}):
        files.append({'name': f"Dados de {escola}"})
    return jsonify({'success': True, 'files': files})

@main_bp.route('/api/delete_file', methods=['POST'])
def delete_file():
    filename = request.json.get('filename', '')
    escola_nome = filename.replace("Dados de ", "")
    app_data = data_manager.load_data(get_session_file())
    
    if escola_nome in app_data.get('schools', {}):
        del app_data['schools'][escola_nome]
        if escola_nome in app_data.get('saved_classes', {}):
            del app_data['saved_classes'][escola_nome]
        if 'unit_annotations' in app_data and escola_nome in app_data['unit_annotations']:
            del app_data['unit_annotations'][escola_nome]
            
        data_manager.save_data(app_data, get_session_file())
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Arquivo não encontrado'})

# ==============================================================================
# 6. API - SALVAR E ANOTAÇÕES
# ==============================================================================

@main_bp.route('/api/save_attendance', methods=['POST'])
def save_attendance():
    try:
        req = request.json
        escola = req.get('escola')
        turma = req.get('turma')
        alunos_lista = req.get('alunos', []) 

        app_data = data_manager.load_data(get_session_file())

        if 'attendance_status' not in app_data: app_data['attendance_status'] = {}
        if 'observations' not in app_data: app_data['observations'] = {}
        if turma not in app_data['attendance_status']: app_data['attendance_status'][turma] = {}
        if turma not in app_data['observations']: app_data['observations'][turma] = {}

        if escola not in app_data['schools']: app_data['schools'][escola] = {}
        if turma not in app_data['schools'][escola]: app_data['schools'][escola][turma] = []
        
        current_students = set(app_data['schools'][escola][turma])

        for aluno in alunos_lista:
            nome = aluno.get('nome')
            app_data['attendance_status'][turma][nome] = aluno.get('presenca')
            app_data['observations'][turma][nome] = aluno.get('observacao')
            
            if nome not in current_students:
                app_data['schools'][escola][turma].append(nome)

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
# 7. API - EXPORTAÇÃO (DRIVE E DOWNLOAD)
# ==============================================================================

@main_bp.route('/api/get_drive_folders', methods=['GET'])
def get_drive_folders_route():
    return drive_service.get_drive_folders()

@main_bp.route('/api/export_excel_drive', methods=['POST'])
def export_excel_drive():
    try:
        req_data = request.json
        escola = req_data.get('escola')
        folder_id = req_data.get('folder_id')
        auto_clear = req_data.get('auto_clear')
        
        session_file = get_session_file()
        app_data = data_manager.load_data(session_file)

        turmas_salvas = app_data.get('saved_classes', {}).get(escola, [])
        if not turmas_salvas:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva'}), 400

        classes_exp = {}
        status_exp = {}
        obs_exp = {}
        
        for turma in turmas_salvas:
            classes_exp[turma] = app_data['schools'].get(escola, {}).get(turma, [])
            status_exp[turma] = app_data['attendance_status'].get(turma, {})
            obs_exp[turma] = app_data['observations'].get(turma, {})

        unit_notes = app_data.get('unit_annotations', {}).get(escola, [])

        excel_buffer = excel_service.export_to_excel(
            classes_exp, status_exp, obs_exp, 
            None, 
            app_data.get('current_user'), 
            app_data.get('periodo'), 
            escola,
            unit_annotations=unit_notes 
        )
        
        filename = excel_service.get_excel_filename(escola, app_data.get('periodo'), app_data.get('current_user'))
        file_id = drive_service.upload_excel_to_drive(excel_buffer.getvalue(), filename, folder_id)
        
        if not file_id:
            return jsonify({'success': False, 'error': 'Erro no upload'}), 500

        if auto_clear:
            app_data = limpar_dados_escola(app_data, escola)
            data_manager.save_data(app_data, session_file)

        return jsonify({'success': True, 'drive_file_id': file_id})

    except Exception as e:
        logger.error(f"Erro export drive: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/export_excel', methods=['GET'])
def export_excel_download():
    """Rota para baixar a Chamada Presencial (chamada.html)."""
    try:
        escola = request.args.get('escola')
        auto_clear = request.args.get('auto_clear') == 'true'
        session_file = get_session_file()
        app_data = data_manager.load_data(session_file)
        
        turmas_salvas = app_data.get('saved_classes', {}).get(escola, [])
        if not turmas_salvas: return "Nenhuma turma salva para exportar", 400

        classes_exp = {}
        status_exp = {}
        obs_exp = {}
        
        for turma in turmas_salvas:
            classes_exp[turma] = app_data['schools'].get(escola, {}).get(turma, [])
            status_exp[turma] = app_data['attendance_status'].get(turma, {})
            obs_exp[turma] = app_data['observations'].get(turma, {})

        unit_notes = app_data.get('unit_annotations', {}).get(escola, [])

        excel_file = excel_service.export_to_excel(
            classes_exp, status_exp, obs_exp, 
            None, 
            app_data.get('current_user'), 
            app_data.get('periodo'), 
            escola,
            unit_annotations=unit_notes
        )

        filename = excel_service.get_excel_filename(escola, app_data.get('periodo'), app_data.get('current_user'))

        if auto_clear:
            app_data = limpar_dados_escola(app_data, escola)
            data_manager.save_data(app_data, session_file)

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
# 8. API - MÓDULO DE ANÁLISE COMPLETO (JS analise.js)
# ==============================================================================

@main_bp.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Recebe arquivos de análise, processa e SALVA na sessão."""
    if 'files[]' not in request.files and 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    files = request.files.getlist('files[]') or request.files.getlist('file')
    all_students_results = []
    processed_count = 0
    errors = []
    
    # Variável para guardar o nome da escola do lote
    school_name = "Escola Desconhecida"
    
    for file in files:
        if not file or file.filename == '': continue
        try:
            content = file.read().decode('utf-8', errors='ignore')
            # Chama o analyzer
            result = analyzer.analyze_attendance_html(content, file.filename)
            
            if result and result.get('student_data'):
                all_students_results.extend(result['student_data'])
                processed_count += 1
                
                if school_name == "Escola Desconhecida" and result.get('school_data'):
                    school_name = result['school_data'].get('unit_name', school_name)
            else:
                errors.append(f"{file.filename}: Sem dados válidos.")
                
        except Exception as e:
            errors.append(f"Erro em {file.filename}: {str(e)}")
            logger.error(f"Erro analisando {file.filename}: {e}")
            
    # Aplica regras de classificação
    final_data = analyzer.apply_classification_rules({'student_data': all_students_results})
    
    # --- SALVANDO NO ARQUIVO COMPARTILHADO ---
    if processed_count > 0:
        session_file = get_session_file()
        app_data = data_manager.load_data(session_file)
        
        if 'analyzed_files' not in app_data:
            app_data['analyzed_files'] = []
            
        # Determina o nome da turma para o lote
        turma_nome = "Múltiplas Turmas"
        if len(files) == 1 and final_data:
            turma_nome = final_data[0].get('turma', 'Geral')
            
        analysis_batch = {
            'id': str(uuid.uuid4()),
            'date': datetime.now().isoformat(),
            'school_name': school_name,
            'student_count': len(final_data),
            'results': final_data, 
            'class_name': turma_nome
        }
        
        app_data['analyzed_files'].append(analysis_batch)
        data_manager.save_data(app_data, session_file)
    
    summary = {
        'total_students': len(final_data),
        'total_files': len(files),
        'processed_files': processed_count,
        'errors': errors,
        'total_absentees': len([s for s in final_data if 'Faltoso' in s['status']]),
        'total_monitors': len([s for s in final_data if 'Monitorar Faltas' in s['status']])
    }
    
    return jsonify({
        'success': True, 
        'results': final_data, 
        'summary': summary
    })

@main_bp.route('/api/get_analyzed_files', methods=['GET'])
def get_analyzed_files():
    """Retorna lista de arquivos/lotes analisados salvos."""
    app_data = data_manager.load_data(get_session_file())
    files = app_data.get('analyzed_files', [])
    
    summary_files = []
    for f in files:
        summary_files.append({
            'id': f.get('id'),
            'date': f.get('date'),
            'school_name': f.get('school_name'),
            'class_name': f.get('class_name'),
            'student_count': f.get('student_count')
        })
        
    return jsonify({'success': True, 'files': summary_files})

@main_bp.route('/api/get_analyzed_file_content/<file_id>', methods=['GET'])
def get_analyzed_file_content(file_id):
    """Retorna os resultados completos de um arquivo analisado específico."""
    app_data = data_manager.load_data(get_session_file())
    files = app_data.get('analyzed_files', [])
    
    for f in files:
        if f.get('id') == file_id:
            return jsonify({'success': True, 'results': f.get('results', [])})
            
    return jsonify({'success': False, 'error': 'Arquivo não encontrado'})

@main_bp.route('/api/delete_analyzed_file/<file_id>', methods=['DELETE'])
def delete_analyzed_file(file_id):
    app_data = data_manager.load_data(get_session_file())
    files = app_data.get('analyzed_files', [])
    
    original_count = len(files)
    app_data['analyzed_files'] = [f for f in files if f.get('id') != file_id]
    
    if len(app_data['analyzed_files']) < original_count:
        data_manager.save_data(app_data, get_session_file())
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Arquivo não encontrado'})

@main_bp.route('/api/clear_analyzed_files', methods=['POST'])
def clear_analyzed_files():
    app_data = data_manager.load_data(get_session_file())
    app_data['analyzed_files'] = []
    data_manager.save_data(app_data, get_session_file())
    return jsonify({'success': True})

# ==============================================================================
# 9. API - DOWNLOAD ANÁLISE
# ==============================================================================

@main_bp.route('/api/download', methods=['POST'])
def api_download_analysis():
    """
    Exporta a tabela de análise atual para Excel (formato do reporter.py).
    Usado na página analise.html
    Nome do arquivo: analise_frequencia_[nome_escola]_dd-mm-aa.xlsx
    """
    try:
        req_data = request.json
        data_rows = req_data.get('data', [])

        show_monthly_details = req_data.get('show_monthly_details', True)
        
        # Passar a opção para o gerador de Excel
        excel_buffer = reporter.generate_analysis_excel(data_rows, show_monthly_details=show_monthly_details)
        
        # Determinar o nome do arquivo
        data_str = datetime.now().strftime("%d-%m-%y")
        
        # Extrair nomes únicos das escolas nos dados
        escolas = list(set([row.get('escola', 'Escola Desconhecida') for row in data_rows]))
        # Remove nulos ou vazios
        escolas = [e for e in escolas if e and e != 'Escola Desconhecida' and e != 'Não identificada']
        
        if len(escolas) == 1:
            raw_name = escolas[0]
            
            # 1. Normaliza unicode
            normalized = unicodedata.normalize('NFKD', raw_name).encode('ASCII', 'ignore').decode('utf-8')
            
            # 2. Substitui tudo que não for letra ou número por underscore
            nome_escola = re.sub(r'[^a-zA-Z0-9]', '_', normalized)
            
            # 3. Remove underscores duplicados 
            nome_escola = re.sub(r'_+', '_', nome_escola).strip('_')
            
            filename = f'analise_frequencia_{nome_escola}_{data_str}.xlsx'
        else:
            # Múltiplas escolas ou desconhecida
            filename = f'analise_frequencia_{data_str}.xlsx'
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Erro export analise: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500