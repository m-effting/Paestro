from flask import Flask, request, jsonify, send_file, render_template
from datetime import datetime
import os
import re
import io
import pickle
from attendance_parser import parse_html_content
from excel_exporter import export_to_excel, get_excel_filename

# Módulos para Google Drive utilizando Service Account
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
    'current_user': None,
    'periodo': None,
    'saved_classes': set()   
}

# ============================================================
# SEÇÃO ADICIONADA PARA GOOGLE DRIVE (INÍCIO)
# ============================================================
# Utilizando Service Account (credenciais não interativas)

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES
)

drive_service = build("drive", "v3", credentials=credentials)

FOLDER_MAP = {
    "ASSOCIAÇÃO JOÃO PAULO II": "1lceON-33pkAk-AN_K0a1-9-yXvk9uwqR",
    "CAIC - PROF FEBRONIO TANCREDO DE OLIVEIRA": "1CBew0EaMYRk1BD1yXwD2zeFgouj19Uv4",
    "CEI AMIGUINHOS DA COMUNIDADE": "1AnJQAWBC4A9jBqNyeMpstLXhZJBw6oEY",
    "CEI ANJINHO DA GUARDA": "1AtFxq441OK5z0B4HnRvZCDFQB0lWOYdw",
    "CEI APRENDER BRINCANDO": "1Jn2TJCRTdae05oyjzCAEAzHUBLpbSKpB",
    "CEI AQUARELA": "15dZQeBfGR9koDjBDiEAQUE-t-IkoCVCr",
    "CEI BOLINHAS DE SABÃO": "16UHzvm-fMEBmM02rlQX8xzpyHsRwmo_E",
    "CEI CAIC": "10bLdh8rqMN-C6PJq9qpS2wn6uSSIGduU",
    "CEI CAMINHO DO APRENDER": "1bLSgp6qkIhn0WKOksWQCIsaGXVzgI0_u",
    "CEI CAMINHO DA IMAGINAÇÃO": "10gHB-mejqYgP5QVGeFgxpb2u-rlNVMyH",
    "CEI CANARINHO": "1va-flnrPHXz94upF63VSSqxTFHkI8QVb",
    "CEI CHAPEUZINHO VERMELHO": "1-szFWrv_3jKFHAKLWm-l9BG75X_BAzod",
    "CEI CIRANDA COLORIDA": "1v7B2rZ_5k_OdO_h7nc_L87Bnd3uGCUUy",
    "CEI CONVIVER": "1VbuRny1r4cIVicttmhPUa_jTILOwaYsR",
    "CEI CRIANÇA FELIZ": "1Qq-zuhSBZqeYPbOviLooMr8zApU1pyD5",
    "CEI DONA MARICOTA": "1ZG2QPKWTE4uxRpbVOHTzD6DRZ_BszP37",
    "CEI ESPAÇO CRIATIVO": "1DT4hwv1lnkQDK1VU5nbHDKXYfGTR8qxj",
    "CEI ESTRELA DO MAR PROF REGINA CAETANA DA SILVEIRA": "1DZ-ssSakfdHXksHKMnmtKUDNIzO3arra",
    "CEI ESTRELINHA": "1BTYzQbLm3zdkdWcxMunWju7-PUhPgdVF",
    "CEI FLORZINHA AZUL": "1_TrZc5Nq2kMRtrnYUOaMXRLPqEZeOHB2",
    "CEI FORMIGUINHA": "1QgCfK0lAt-3o3J5_WUoJn8jQ8xqLMfip",
    "CEI INOVAÇÃO": "104UWCNCrPRiodkiAVJ15fcHgLbfM73WN",
    "CEI INTERAÇÃO": "1eSgJqZ9dSbPlb4fnqRIkR8sg557sdQp0",
    "CEI JOSÉ MIGUEL FERREIRA": "1A3_MZvGYWejbqM_n9e218Yw5EKVo01nm",
    "CEI MUNDO ENCANTADO": "1ZJV9zJcmr3G-hbO0w3DDzMoFv6C2XJsR",
    "CEI MUNDO MÁGICO": "1a8zl1UfcuX4d23VLv0TDFG5cuJmcWVXI",
    "CEI MARIA DOS SANTOS SILVA": "1ttPZDyN8IhV9IdAGQdpUk8UdEcdmpYef",
    "CEI MARIA JOSÉ DE MEDEIROS": "1iLmmKNx6lCjSCxOxA8XdoXxV1MOpuNDa",
    "CEI NOVA ESPERANÇA": "13UaBcioA29p56VhiC5d7Admagmh9e2kp",
    "CEI NOVA GERAÇÃO": "1r-ApZx5VKADYLGRBOo2OJk7Z0gp-niwu",
    "CEI PADRE RÉUS": "1mqw91sslr5Ko4K4Cy5pE95BmsIQScykU",
    "CEI PARAÍSO": "1rYevTkqGZHtuzosSutsFLpZA6c4wdBn6",
    "CEI PARAÍSO DO AMOR": "1UkdML6aFX9h31j9aJWylywofDmeCndkX",
    "CEI PRIMEIROS PASSOS": "1sgqCIScyrMcHfQVcwBRONqe5-BFP2zrW",
    "CEI PROF ARGEMIRA DE FARIAS DA SILVEIRA": "1_YoLuJSw-Cc33h94wRBnV6rG9sZZWe1L",
    "CEI PROF AURORA DA SILVA LOPES": "1ayOfMuvhNzeJRtz1xGkFbEq8WTrvLkYw",
    "CEI PROF INÊS MARTA DA SILVA": "12tWNdKLkkA_DdC9COdjHu2aHbmg_Pmqf",
    "CEI PROF PAULO BRAULIO GOULART": "1xZ4VT3yaIXnGZ2sLJe33gwdjVSN_D1fk",
    "CEI REALIZAR": "1XjoBKDU0cp4AmCKq4YfR-L-MpeYmG6gZ",
    "CEI RODA VIVA": "1d-Yyp7dG77GcIfbfLl80kZ54dI8hQLjm",
    "CEI ROMEU E JULIETA": "1cDzd5FdGg96DzZA9uWSO5bytLhfqUMBR",
    "CEI SANTA MARTA": "1SRa-BloTjltMlTfMnIOxhk2APiXwyPD2",
    "CEI SÃO TOMÉ": "16lAIQuHMkWz_R_NRbZ517fntJWQrZMTl",
    "CEI SNOOPY": "1wO3zYTfszoJY2sWLWFX7vFxUO7VBZ8dl",
    "CEI ULISSES GUIMARÃES": "1a8NHkVW9CmZmiF4d4rJLJvkFGjfS7j4X",
    "CEI VALE VERDE PROF. MAURICIO SCHMITT": "1N52QSgfdy3vhEHE6UqWxT_qZ-qFyIPcZ",
    "CEI VIDA MELHOR": "14fAJX6Fm8wQgkgvhuy6sZRHF0B5857u0",
    "CEI VÓ LAURA": "1U7V-23QiyG7j4KHUJ0_jB4rw4-BnP0Cp",
    "CEI VOO LIVRE": "1dPGRQH9fjM52tD7pGAZ671JDkJkm532X",
    "CEI VOVÓ MARIA": "1T5TTN7uNDr17Zs2kIlj_DW0z_CnBipmt",
    "CEI VOVÓ DOLORES": "1J1NT1SrM1H4l32um4v-sIzdBwEppoPrJ",
    "EB ABÍLIO MANOEL DE ABREU": "1B1rc61ao6jGYc5lx8S5v2zG6Tcj7jAMK",
    "EB ANTONIETA SILVEIRA DE SOUZA": "17DzosmvTVTMJsCrwn-ZX9-45qMQhwIxW",
    "EB FREI DAMIÃO": "1zQx5U-zsOfSfmnTUo30Ffh1k7Qp2yzy8",
    "EB NERI BRASILIANO MARTINS": "1kIVVdS-qS-h7wPCkIpxEcUw8WgBbo656",
    "EB NOSSA SENHORA DE FÁTIMA": "1KYAyTdSVVjU9ZNh2J0l63eU6b1cLVvKB",
    "EB PROF FRANCISCA RAIMUNDA FARIAS DA COSTA": "19CPUW5k1dK2iY2t5WiohciA7GL7iagfq",
    "EB PROF LAURITA WAGNER DA SILVEIRA": "1H98U2UiW-2FEVPbsnUiKOGRS2dg5k1uq",
    "EB PROFª ADRIANA WEINGARTNER": "1e-rtvJqKFMedGXJlD9l-UkUE1pcFyjCl",
    "EB VIVIANE LAURITA DE QUADROS COELHO": "1EmA2TF4aRXZFiOtc1RPCCTa4nG7QqwA8",
    "EBM PROF MARA LUIZA VIEIRA LIBERATO": "1igrWoX699aboGZ86LGiivRRg-7fBul_T",
    "EBM PROF. OSMAR ANTÔNIO VIEIRA": "1oF0F0mnotfaEe72OPgQYETerJSGvv2pB",
    "EBM REINALDO WEINGARTNER": "1UpN4_iJ6pc6ETMDGhgEGPi2DAVL45-y5",
    "EI DO RINCÃO": "18-JqrK_DfuSvfTFpWgiAmEQUMtTCArw_",
    "ER ALBARDÃO": "14aZayeFnpD8qKhgqMNltltw_BFtGivqt",
    "ER BENTO JOSÉ DO NASCIMENTO": "1E2UE8ne44jaAlJ2LuBoZs-kaxDWwEioa",
    "ER DANIEL CARLOS WEINGARTNER": "12i7OyObNXdQLvtR6dTa7JEJfjk_9i7qr",
    "ER ISABEL BOTELHO DE PAULO": "1_vmcQugDurwQfSvAhqIVPeM4j4ILgGCm",
    "ER MANOEL DA SILVA": "1RVyCidQyRewBbk-s0H4-Lp1WyhSCh2Au",
    "ER OLGA CERINO": "14WYgP_R9I9CfKNshUkGYGXZS8dOFmyCf",
    "FUNDAÇÃO FÉ E ALEGRIA DO BRASIL": "1pKN8Ukf9fiInysN-r94z91XkI8z-mM5b",
    "GE EVANDA SUELLI JUTTEL MACHADO": "1cmyPQeZP3fF2BUS85Y8cx5CcA0jvGjvv",
    "GE GUILHERME WIETHORN FILHO": "1DR0o8J1DYkQLgigWTzjgDNgk54uVvvRz",
    "GE NAJLA CARONE GUEDERT": "1EJLUQoiiTpOw6QAbMBokUlyRjdUQLWaL",
    "GE PEQUENO PRÍNCIPE": "1v3pwUajWs28jRCqa6Hl0ruNqeac8gSxV",
    "GE PROF MARIA LUZIA DE SOUZA": "1Jii-YViEMEcP6kCtgNZ_dHACizLMuNQU",
    "GE TEREZINHA MARIA ESPÍNDOLA MARTINS": "1qOpWETmx8J0Q3R6QCfbKmTWGDpDfyCCB"
}

def upload_excel_to_drive(excel_data, file_name, folder_id=None):
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(excel_data),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable=True
    )

    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')
# ============================================================
# SEÇÃO ADICIONADA PARA GOOGLE DRIVE (FIM)
# ============================================================

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

@app.route('/api/get_saved_classes_status', methods=['GET'])
def get_saved_classes_status():
    return jsonify({
        'success': True,
        'saved_classes': list(app_data['saved_classes'])
    })

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
            for turma in app_data['schools'][filename].keys():
                app_data['saved_classes'].discard(turma)
            
            del app_data['schools'][filename]
            del app_data['html_content'][filename]
            
            turmas_para_remover = set()
            for turma in app_data['attendance_status'].keys():
                if turma in app_data['schools'].get(filename, {}):
                    turmas_para_remover.add(turma)
            
            for turma in turmas_para_remover:
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

@app.route('/api/get_saved_classes', methods=['GET'])
def get_saved_classes():
    return jsonify({
        'success': True,
        'saved_classes': list(app_data['saved_classes'])
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
            
            if nome not in app_data['schools'][escola][turma]:
                app_data['schools'][escola][turma].append(nome)
            
            app_data['attendance_status'][turma][nome] = aluno['presenca']
            app_data['observations'][turma][nome] = aluno['observacao']
        
        app_data['saved_classes'].add(turma)
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
        # Obtém parâmetros da requisição ou dados armazenados
        escola_selecionada = request.args.get('escola')
        periodo = request.args.get('periodo') or app_data.get('periodo', 'indefinido')
        current_user = app_data.get('current_user', 'indefinido')
        auto_clear = request.args.get('auto_clear', 'false').lower() == 'true'

        # Validação de turmas salvas
        if not app_data['saved_classes']:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'})

        # Organiza turmas por escola
        turmas_por_escola = {}
        for turma in app_data['saved_classes']:
            for escola, turmas in app_data['schools'].items():
                if turma in turmas:
                    if escola not in turmas_por_escola:
                        turmas_por_escola[escola] = []
                    turmas_por_escola[escola].append(turma)
                    break

        # Se uma escola específica foi solicitada, filtra por ela
        if escola_selecionada and escola_selecionada in turmas_por_escola:
            turmas_por_escola = {escola_selecionada: turmas_por_escola[escola_selecionada]}

        if not turmas_por_escola:
            return jsonify({'success': False, 'error': 'Nenhuma turma válida encontrada'})

        # Prepara dados para exportação
        classes_to_export = {}
        attendance_to_export = {}
        observations_to_export = {}

        for escola, turmas in turmas_por_escola.items():
            for turma in turmas:
                classes_to_export[turma] = app_data['schools'][escola][turma]
                attendance_to_export[turma] = app_data['attendance_status'].get(turma, {})
                observations_to_export[turma] = app_data['observations'].get(turma, {})

        # Gera o Excel
        output = export_to_excel(
            classes_to_export,
            attendance_to_export,
            observations_to_export,
            None,  # Não envia o HTML content
            current_user,
            periodo,
            escola_selecionada or list(turmas_por_escola.keys())[0]
        )

        # Limpeza após exportação
        if auto_clear:
            for turma in classes_to_export:
                app_data['attendance_status'].pop(turma, None)
                app_data['observations'].pop(turma, None)
                app_data['saved_classes'].discard(turma)

        return send_file(
            output,
            as_attachment=True,
            download_name=get_excel_filename(escola_selecionada, periodo, current_user),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
# ============================================================
# NOVOS ENDPOINTS PARA DRIVE (INÍCIO)
# ============================================================
@app.route('/api/get_drive_folders', methods=['GET'])
def get_drive_folders():
    try:
        folder_list = [{'id': v, 'name': k} for k, v in FOLDER_MAP.items()]
        return jsonify({'success': True, 'folders': folder_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export_excel_drive', methods=['POST'])
def export_attendance_drive():
    try:
        data = request.json
        folder_id = data.get('folder_id')
        escola_selecionada = data.get('escola')

        if not folder_id:
            return jsonify({'success': False, 'error': 'Nenhum folder_id fornecido'})

        # Lógica idêntica à export_excel
        if not app_data['saved_classes']:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'})
        
        classes_to_export = {}
        attendance_to_export = {}
        observations_to_export = {}
        
        if not escola_selecionada and app_data['schools']:
            escola_selecionada = next(iter(app_data['schools'].keys()))
        
        for turma in app_data['saved_classes']:
            escola_da_turma = None
            for escola, turmas in app_data['schools'].items():
                if turma in turmas:
                    escola_da_turma = escola
                    break
            
            if escola_da_turma and (not escola_selecionada or escola_da_turma == escola_selecionada):
                classes_to_export[turma] = app_data['schools'][escola_da_turma][turma]
                attendance_to_export[turma] = app_data['attendance_status'].get(turma, {})
                observations_to_export[turma] = app_data['observations'].get(turma, {})
                escola_selecionada = escola_da_turma
        
        if not classes_to_export:
            return jsonify({'success': False, 'error': 'Nenhuma turma válida encontrada para exportação'})
        
        periodo = data.get('periodo') or app_data.get('periodo', 'Não informado')
        current_user = app_data.get('current_user', 'indefinido')
        
        output = export_to_excel(
            classes_to_export,
            attendance_to_export,
            observations_to_export,
            app_data['html_content'].get(escola_selecionada),
            current_user,
            periodo,
            escola_selecionada
        )
        
        excel_data = output.getvalue()
        file_name = get_excel_filename(escola_selecionada, periodo, current_user)
        
        drive_id = upload_excel_to_drive(excel_data, file_name, folder_id)
        return jsonify({'success': True, 'drive_file_id': drive_id})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
# ============================================================
# NOVOS ENDPOINTS PARA DRIVE (FIM)
# ============================================================

if __name__ == '__main__':
    import os
    print(f"Template folder: {app.template_folder}")
    print(f"Static folder: {app.static_folder}")
    print(f"Templates existentes: {os.listdir(app.template_folder)}")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
