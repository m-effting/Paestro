import os
import io
import json
import logging
from flask import request, jsonify
from .excel_exporter import export_to_excel, get_excel_filename

# Variável para controlar se temos Google Drive habilitado
DRIVE_ENABLED = False
drive_service = None

# ==============================================================================
# CONFIGURAÇÃO DE AUTENTICAÇÃO (SERVICE ACCOUNT - MODO WEB)
# Isso permite que o app funcione no Render, Tablet e Celular sem abrir navegador
# ==============================================================================
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    
    # Pega as credenciais da variável de ambiente (Service Account)
    json_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    
    if json_creds:
        # Escopos necessários
        SCOPES = ['https://www.googleapis.com/auth/drive']
        
        try:
            # Tenta carregar como JSON string (configuração do Render)
            creds_dict = json.loads(json_creds)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
        except json.JSONDecodeError:
            # Se falhar, tenta carregar como caminho de arquivo (configuração Local)
            credentials = service_account.Credentials.from_service_account_file(
                json_creds, scopes=SCOPES
            )

        drive_service = build('drive', 'v3', credentials=credentials)
        DRIVE_ENABLED = True
        print("✅ Google Drive conectado (Modo Service Account)!")
    else:
        print("⚠️ Variável GOOGLE_CREDENTIALS_JSON não encontrada.")

except ImportError:
    print("❌ Bibliotecas do Google não instaladas.")
except Exception as e:
    print(f"❌ Erro ao conectar no Drive: {str(e)}")

# ==============================================================================
# MAPA DE PASTAS DAS ESCOLAS
# IMPORTANTE: Se você criou pastas novas, atualize os IDs abaixo!
# ==============================================================================
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
    "CEI FORMIGUINHAS": "1QgCfK0lAt-3o3J5_WUoJn8jQ8xqLMfip",
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
    """Faz upload de um arquivo Excel para o Google Drive."""
    if not DRIVE_ENABLED or not drive_service:
        return "drive-not-available"
        
    try:
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(excel_data),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resumable=True
        )

        file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True
        ).execute()

        return file.get('id')
    except Exception as e:
        logging.error(f"Erro ao fazer upload para o Drive: {str(e)}")
        return None

def get_drive_folders():
    """Retorna a lista de pastas disponíveis no Google Drive."""
    if not DRIVE_ENABLED:
        return jsonify({
            'success': False, 
            'error': 'Google Drive não está habilitado nesta instalação.',
            'folders': []
        })
    
    try:
        folder_list = [{'id': v, 'name': k} for k, v in FOLDER_MAP.items()]
        return jsonify({'success': True, 'folders': folder_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def export_attendance_drive(app_data):
    """Faz upload de um arquivo Excel para o Google Drive se o Drive estiver habilitado."""
    if not DRIVE_ENABLED:
        return jsonify({
            'success': False, 
            'error': 'Google Drive não está habilitado nesta instalação.',
            'alternate_message': 'Você pode fazer download do arquivo manualmente.'
        }), 400
        
    try:
        # Obtém dados da requisição
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'Nenhum dado fornecido'}), 400

        folder_id = data.get('folder_id')
        escola_selecionada = data.get('escola')
        auto_clear = data.get('auto_clear', False)

        # Validação explícita de folder_id
        if not folder_id or not folder_id.strip():
            return jsonify({'success': False, 'error': 'Nenhum folder_id válido fornecido'}), 400

        # Verifica se há turmas salvas
        if 'saved_classes' not in app_data or not app_data['saved_classes']:
            return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'}), 400

        # Define as turmas salvas a serem usadas
        if escola_selecionada:
            if escola_selecionada not in app_data['saved_classes']:
                return jsonify({'success': False, 'error': 'Nenhuma turma salva para a escola selecionada'}), 400
            turmas_salvas = app_data['saved_classes'][escola_selecionada]
        else:
            turmas_salvas = set().union(*app_data['saved_classes'].values())
            if not turmas_salvas:
                return jsonify({'success': False, 'error': 'Nenhuma turma salva para exportação'}), 400

        # Prepara os dados para exportação
        classes_to_export = {}
        attendance_to_export = {}
        observations_to_export = {}

        for turma in turmas_salvas:
            for escola, turmas in app_data['schools'].items():
                if turma in turmas:
                    if escola_selecionada and escola != escola_selecionada:
                        continue
                    classes_to_export[turma] = app_data['schools'][escola][turma]
                    attendance_to_export[turma] = app_data['attendance_status'].get(turma, {})
                    observations_to_export[turma] = app_data['observations'].get(turma, {})
                    break

        # Verifica se há turmas válidas
        if not classes_to_export:
            return jsonify({'success': False, 'error': 'Nenhuma turma válida encontrada'}), 400

        # Obtém período e usuário
        periodo = data.get('periodo') or app_data.get('periodo', 'Não informado')
        current_user = app_data.get('current_user', 'indefinido')

        # Gera o arquivo Excel
        output = export_to_excel(
            classes_to_export,
            attendance_to_export,
            observations_to_export,
            app_data.get('html_content', {}).get(escola_selecionada) if escola_selecionada else None,
            current_user,
            periodo,
            escola_selecionada or "Todas as Escolas"
        )

        # Faz o upload para o Google Drive
        excel_data = output.getvalue()
        file_name = get_excel_filename(escola_selecionada or "Todas as Escolas", periodo, current_user)
        drive_file_id = upload_excel_to_drive(excel_data, file_name, folder_id)
        
        if not drive_file_id or drive_file_id == "drive-not-available":
            return jsonify({
                'success': False, 
                'error': 'Erro no upload. Verifique se o Robô tem permissão de Editor na pasta do Drive.'
            }), 500

        # Realiza limpeza se solicitado
        if auto_clear:
            if escola_selecionada and escola_selecionada in app_data['saved_classes']:
                app_data['saved_classes'][escola_selecionada].clear()
            else:
                app_data['saved_classes'].clear()
            
            # Limpa status apenas das turmas exportadas
            for turma in classes_to_export:
                app_data['attendance_status'].pop(turma, None)
                app_data['observations'].pop(turma, None)

        return jsonify({
            'success': True,
            'drive_file_id': drive_file_id
        }), 200

    except Exception as e:
        logging.error(f"Erro ao exportar para o Drive: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500