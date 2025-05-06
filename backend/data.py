import unicodedata

# Função para normalizar nomes das escolas
def normalize_school_name(name):
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return name.lower().strip()


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
    'saved_classes': {},
    'unit_annotations': {},
    # Armazenamento global de arquivos analisados (legado, será redirecionado para sessão de usuário)
    'analyzed_files': []  
}