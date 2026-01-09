import json
import os
import logging
import unicodedata

# Configuração de Logger
logger = logging.getLogger(__name__)

def normalize_school_name(name):
    """
    Normaliza nomes de escolas (remove acentos, minúsculas).
    Útil para chaves de dicionário consistentes.
    """
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return name.lower().strip()

def load_data(filepath):
    """
    Carrega os dados a partir do arquivo JSON compartilhado.
    Se o arquivo não existir ou estiver corrompido, retorna uma estrutura vazia padrão.
    """
    default_structure = {
        'schools': {},           # Estrutura: {NomeEscola: {Turma: [Alunos]}}
        'saved_classes': {},     # Turmas que já tiveram chamada salva {Escola: [Turmas]}
        'attendance_status': {}, # {Turma: {Aluno: Status}} (P, F, FJ)
        'observations': {},      # {Turma: {Aluno: Obs}}
        'html_content': {},      # Conteúdo HTML bruto para exportação
        'unit_annotations': {},  # Anotações gerais da unidade
        'current_user': None,
        'periodo': None,
        'analyzed_files': []     # Resultados da análise de busca ativa
    }

    if not os.path.exists(filepath):
        return default_structure

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Garante que chaves essenciais existam (caso o JSON seja antigo)
            for key, val in default_structure.items():
                if key not in data:
                    data[key] = val
            return data
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Erro ao carregar dados de {filepath}: {e}")
        return default_structure

def save_data(data, filepath):
    """
    Salva os dados no arquivo JSON compartilhado.
    Isso garante que o Tablet A veja o que o Tablet B fez.
    """
    try:
        # Garante que o diretório existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar dados em {filepath}: {e}")
        return False

def merge_data(current_data, new_data_from_parser):
    """
    Mescla os dados novos vindos de um upload (parser) com os dados já existentes.
    Não apaga o que já estava lá, apenas adiciona ou atualiza.
    """
    if not new_data_from_parser or 'schools' not in new_data_from_parser:
        return current_data

    # Mescla escolas e turmas
    for escola, turmas in new_data_from_parser['schools'].items():
        if escola not in current_data['schools']:
            current_data['schools'][escola] = {}
        
        for turma, alunos in turmas.items():
            # Atualiza lista de alunos para essa turma
            current_data['schools'][escola][turma] = alunos

    return current_data