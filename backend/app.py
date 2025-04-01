from flask import Flask, request, jsonify, send_file, render_template
from datetime import datetime
import os
import re
import io
import pickle
from attendance_parser import parse_html_content
from excel_exporter import export_to_excel, get_excel_filename
from drive_exporter import get_drive_folders, export_attendance_drive 
from threading import Lock

save_lock = Lock()


app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'))

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'senha_ultramente_secreta'

app_data = {
    'schools': {},         
    'selected_school': None,
    'selected_class': None,
    'attendance_status': {},  
    'observations': {},       
    'file_uploaded': False,
    'html_content': {},       
    'periodo': None,
    'saved_classes': {}  
}

@app.route('/')
def home():
    return render_template('index.html', now=datetime.now())

@app.route('/importar')
def import_page():
    return render_template('importar.html')

@app.route('/chamada')
def attendance_page():
    return render_template('chamada.html',
                         current_user=app_data['current_user'],
                         current_date=datetime.now().strftime('%d/%m/%Y'))

@app.route('/api/get_saved_classes', methods=['GET'])
def get_saved_classes():
    try:
        escola = request.args.get('escola')
        if escola:
            # Retorna apenas as turmas salvas da escola especificada
            if escola in app_data['saved_classes']:
                return jsonify({
                    'success': True,
                    'saved_classes': list(app_data['saved_classes'][escola])
                })
            else:
                return jsonify({
                    'success': True,
                    'saved_classes': []
                })
        else:
            # Retorna todas as turmas salvas de todas as escolas como uma lista plana
            all_saved = [turma for escola_turmas in app_data['saved_classes'].values() for turma in escola_turmas]
            return jsonify({
                'success': True,
                'saved_classes': list(all_saved)
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 1000


@app.route('/api/get_saved_classes_status', methods=['GET'])
def get_saved_classes_status():
    try:
        # Retorna todas as turmas salvas de todas as escolas
        all_saved = [turma for escola_turmas in app_data['saved_classes'].values() for turma in escola_turmas]
        return jsonify({
            'success': True,
            'saved_classes': all_saved
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    app_data['current_user'] = data.get('username')
    app_data['periodo'] = data.get('periodo')
    return jsonify({
        'success': True, 
        'username': app_data['current_user'],
        'periodo': app_data['periodo']
    })

@app.route('/api/upload', methods=['POST'])
def handle_file_upload():
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'})
    
    files = request.files.getlist('files')
    if not files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
    
    try:
        for file in files:
            if file.filename == '':
                continue
            
            try:
                html_content = file.read().decode('utf-8')
            except UnicodeDecodeError:
                return jsonify({'success': False, 'error': 'Erro de codificação no arquivo'})
            
            # Passa o nome do arquivo para o parser como fallback
            classes_dict, unidade_name = parse_html_content(html_content, file.filename)
            
            # Remove caracteres problemáticos mas mantém acentos
            school_name = re.sub(r'[\\/*?:"<>|]', '', unidade_name).strip()
            school_name = ' '.join(school_name.split())
            
            if not school_name:
                school_name = os.path.splitext(file.filename)[0]
            
            if school_name not in app_data['schools']:
                app_data['schools'][school_name] = {}
            
            app_data['schools'][school_name].update(classes_dict)
            app_data['html_content'][school_name] = html_content
            if not school_name:
                school_name = os.path.splitext(file.filename)[0]
            
            for turma, alunos in classes_dict.items():
                if turma not in app_data['attendance_status']:
                    app_data['attendance_status'][turma] = {}
                if turma not in app_data['observations']:
                    app_data['observations'][turma] = {}
                
                for aluno in alunos:
                    if aluno not in app_data['attendance_status'][turma]:
                        app_data['attendance_status'][turma][aluno] = 'P'
                    if aluno not in app_data['observations'][turma]:
                        app_data['observations'][turma][aluno] = ''
        
        app_data['file_uploaded'] = True
        return jsonify({
            'success': True,
            'schools': list(app_data['schools'].keys()),
            'message': 'Arquivos processados com sucesso'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/get_current_user', methods=['GET'])
def get_current_user():
    return jsonify({
        'success': True,
        'username': app_data.get('current_user', ''),
        'periodo': app_data.get('periodo', '')
    })

@app.route('/api/get_imported_files', methods=['GET'])
def get_imported_files():
    try:
        files = [{'name': escola} for escola in app_data['schools'].keys()]
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'error': 'Nome do arquivo não fornecido'})
        
        if filename in app_data['schools']:
            # Captura as turmas associadas antes de deletar
            turmas_da_escola = set(app_data['schools'][filename].keys())
            
            # Remove a entrada da escola em saved_classes, se existir
            if filename in app_data['saved_classes']:
                del app_data['saved_classes'][filename]
            
            # Remove a escola e seu conteúdo
            del app_data['schools'][filename]
            del app_data['html_content'][filename]
            
            # Remove turmas associadas de attendance_status e observations
            for turma in turmas_da_escola:
                app_data['attendance_status'].pop(turma, None)
                app_data['observations'].pop(turma, None)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Arquivo não encontrado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/get_schools', methods=['GET'])
def get_schools():
    return jsonify({
        'success': True,
        'schools': list(app_data['schools'].keys())
    })

@app.route('/api/get_school_classes', methods=['POST'])
def get_school_classes():
    data = request.get_json()
    school = data.get('school')
    
    if not school or school not in app_data['schools']:
        return jsonify({'success': False, 'error': 'Escola não encontrada'})
    
    return jsonify({
        'success': True,
        'classes': list(app_data['schools'][school].keys()),
        'saved_classes': list(app_data['saved_classes'])
    })

@app.route('/api/get_class', methods=['POST'])
def get_class_data():
    data = request.get_json()
    school = data.get('school')
    turma = data.get('class')
    
    if not school or school not in app_data['schools']:
        return jsonify({'success': False, 'error': 'Escola não encontrada'})
    
    if turma not in app_data['schools'][school]:
        return jsonify({'success': False, 'error': 'Turma não encontrada'})
    
    alunos_originais = app_data['schools'][school][turma]
    alunos_data = []
    
    for aluno in alunos_originais:
        alunos_data.append({
            'nome': aluno,
            'presenca': app_data['attendance_status'].get(turma, {}).get(aluno, 'P'),
            'observacao': app_data['observations'].get(turma, {}).get(aluno, '')
        })
    
    return jsonify({
        'success': True,
        'alunos': alunos_data,
        'turma': turma,
        'total_alunos': len(alunos_data)
    })

@app.route('/api/get_turmas', methods=['GET'])
def get_turmas():
    return jsonify({
        'success': True,
        'turmas': list(app_data.get('classes', {}).keys())
    })

@app.route('/api/save_attendance', methods=['POST'])
def save_attendance_data():

    data = request.json
    escola = data.get('escola')
    turma = data.get('turma')
    alunos = data.get('alunos')
    
    if not all([escola, turma, alunos]):
        return jsonify({'success': False, 'error': 'Dados incompletos'})
    
    try:
        if escola not in app_data['schools']:
            app_data['schools'][escola] = {}
        
        if turma not in app_data['schools'][escola]:
            app_data['schools'][escola][turma] = []
        
        if turma not in app_data['attendance_status']:
            app_data['attendance_status'][turma] = {}
        if turma not in app_data['observations']:
            app_data['observations'][turma] = {}
        
        for aluno in alunos:
            nome = aluno['nome']
            presenca = aluno['presenca']
            observacao = aluno['observacao']
            
            # Adiciona o aluno à lista da turma, se ainda não estiver presente
            if nome not in app_data['schools'][escola][turma]:
                app_data['schools'][escola][turma].append(nome)
            
            # Atualiza presença e observação no backend
            app_data['attendance_status'][turma][nome] = presenca
            app_data['observations'][turma][nome] = observacao
        
        # Adiciona a turma ao conjunto de turmas salvas da escola específica
        if escola not in app_data['saved_classes']:
            app_data['saved_classes'][escola] = set()
        app_data['saved_classes'][escola].add(turma)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/clear_saved_classes', methods=['POST'])
def clear_saved_classes():
    try:
        print("Iniciando limpeza de turmas salvas...")
        print(f"Turmas salvas antes: {app_data['saved_classes']}")
        
        app_data['saved_classes'].clear()
        
        print(f"Turmas salvas depois: {app_data['saved_classes']}")
        print("Limpeza concluída com sucesso!")
        
        return jsonify({
            'success': True,
            'message': 'Todas as turmas salvas foram removidas',
            'saved_classes': list(app_data['saved_classes'])
        })
    except Exception as e:
        print(f"ERRO ao limpar turmas: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/exportar')
def export_page():
    escola = request.args.get('escola', '')  
    return render_template('exportar.html',
                         escola=escola,  
                         current_user=app_data['current_user'],
                         current_date=datetime.now().strftime('%d/%m/%Y'))

@app.route('/api/export_excel', methods=['GET'])
def export_attendance():
    try:
        # Obtém parâmetros da requisição ou valores padrão
        escola_selecionada = request.args.get('escola')
        periodo = request.args.get('periodo') or app_data.get('periodo', 'indefinido')
        current_user = app_data.get('current_user', 'indefinido')
        auto_clear = request.args.get('auto_clear', 'false').lower() == 'true'

        # Verifica se há turmas salvas em app_data
        if 'saved_classes' not in app_data or not app_data['saved_classes']:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'})

        # Define as turmas salvas a serem usadas
        if escola_selecionada:
            # Filtra turmas salvas da escola selecionada
            if escola_selecionada not in app_data['saved_classes'] or not app_data['saved_classes'][escola_selecionada]:
                return jsonify({'success': False, 'error': 'Nenhuma turma salva para a escola selecionada'})
            turmas_salvas = app_data['saved_classes'][escola_selecionada]
        else:
            # Usa todas as turmas salvas de todas as escolas
            turmas_salvas = set().union(*app_data['saved_classes'].values())
            if not turmas_salvas:
                return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'})

        # Prepara os dados para exportação
        classes_to_export = {}
        attendance_to_export = {}
        observations_to_export = {}

        for turma in turmas_salvas:
            for escola, turmas in app_data['schools'].items():
                if turma in turmas:
                    # Filtra por escola, se especificada
                    if escola_selecionada and escola != escola_selecionada:
                        continue
                    classes_to_export[turma] = app_data['schools'][escola][turma]
                    attendance_to_export[turma] = app_data['attendance_status'].get(turma, {})
                    observations_to_export[turma] = app_data['observations'].get(turma, {})
                    break

        # Verifica se há turmas válidas para exportar
        if not classes_to_export:
            return jsonify({'success': False, 'error': 'Nenhuma turma válida encontrada para exportação'})

        # Gera o arquivo Excel
        output = export_to_excel(
            classes_to_export,
            attendance_to_export,
            observations_to_export,
            None,  # Não envia o HTML content
            current_user,
            periodo,
            escola_selecionada or "Todas as Escolas"
        )

        # Realiza limpeza, se solicitado
        if auto_clear:
            if escola_selecionada:
                app_data['saved_classes'][escola_selecionada].clear()
            else:
                app_data['saved_classes'].clear()
            for turma in classes_to_export:
                app_data['attendance_status'].pop(turma, None)
                app_data['observations'].pop(turma, None)

        # Retorna o arquivo Excel
        return send_file(
            output,
            as_attachment=True,
            download_name=get_excel_filename(escola_selecionada or "Todas as Escolas", periodo, current_user),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Registrando os endpoints do Drive
app.route('/api/get_drive_folders', methods=['GET'])(get_drive_folders)
app.route('/api/export_excel_drive', methods=['POST'])(lambda: export_attendance_drive(app_data))

if __name__ == '__main__':
    import os
    print(f"Template folder: {app.template_folder}")
    print(f"Static folder: {app.static_folder}")
    print(f"Templates existentes: {os.listdir(app.template_folder)}")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)