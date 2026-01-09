from lxml import html
import re
import os
import logging

# Configuração de Logger para rastreamento de erros no processamento
logger = logging.getLogger(__name__)

def parse_chamada(html_content, filename=None):
    """
    Extrai turmas, alunos e nome da unidade especificamente de relatórios de CHAMADA.
    
    Args:
        html_content (str): Conteúdo HTML bruto do EducarWeb.
        filename (str): Nome do arquivo original para fallback.

    Returns:
        dict: Estrutura padronizada {'schools': {unidade: {turma: [alunos]}}}
    """
    
    # Validação de integridade do conteúdo recebido
    if not html_content or not isinstance(html_content, (str, bytes)):
        return {}, os.path.splitext(filename)[0] if filename else "Unidade não identificada"

    try:
        tree = html.fromstring(html_content)
    except Exception as e:
        logger.error(f"Erro ao converter HTML para árvore lxml: {e}")
        return {}, os.path.splitext(filename)[0] if filename else "Unidade não identificada"

    classes = {}
    current_turma = None
    unidade_name = None
    
    # Regex para identificar padrões de Turma e capturar unidade entre parênteses
    TURMA_REGEX = re.compile(
        r'Turma:\s*((\d+\s*[\u00ba\u00aa]*\s*ANO\s*-\s*\d+)|([^(\n]+))\s*(?:\(([^)\n]+)|$)',
        re.UNICODE
    )
    
    # 1. Identificação da Unidade Escolar (Tentativa via Tags de Cabeçalho)
    possible_name_locations = [
        tree.xpath("//title/text()"),
        tree.xpath("//h1/text()"),
        tree.xpath("//h2/text()"),
        tree.xpath("//div[contains(@class, 'header')]//text()"),
        tree.xpath("//span[contains(@class, 'school-name')]//text()")
    ]

    for location in possible_name_locations:
        if location and not unidade_name:
            text = ' '.join([t.strip() for t in location if t.strip()])
            if text and "Turma:" not in text and "Total" not in text:
                unidade_name = re.sub(r'-\s*$', '', text.split('-')[0] if '-' in text else text).strip()
                break

    # 2. Processamento de Tabelas de Alunos
    tables = tree.xpath("//table[contains(@class, 'jrPage')]")
    
    for table in tables:
        rows = table.xpath(".//tr")
        turma_row = None
        
        # Localiza a linha que define o início de uma nova turma
        for row in rows:
            row_text = ' '.join(row.itertext()).strip()
            if "Turma:" in row_text and "Total de Matrículas" not in row_text:
                turma_row = row
                break
        
        if turma_row is not None:
            turma_text = ' '.join(turma_row.itertext()).strip()
            match = TURMA_REGEX.search(turma_text)
            
            if match:
                current_turma = match.group(1).strip()
                
                # Tentativa de extrair unidade caso esteja no formato "Turma X (Unidade Y)"
                if match.group(4):
                    unidade_candidate = re.sub(r'-\s*$', '', match.group(4).strip()).strip()
                    if unidade_candidate and not unidade_name:
                        unidade_name = unidade_candidate
                
                if current_turma not in classes:
                    classes[current_turma] = []
        
        if not current_turma:
            continue
        
        # 3. Identificação das colunas da tabela de alunos
        header_row = None
        header_index = None
        for idx, row in enumerate(rows):
            text = row.text_content().strip()
            if "Código" in text and "Nome" in text:
                header_row = row
                header_index = idx
                break
        
        if header_row is None:
            continue
        
        # Localiza o índice da coluna "Nome"
        header_cells = header_row.xpath(".//th") or header_row.xpath(".//td")
        nome_index = next((i for i, c in enumerate(header_cells) if "Nome" in c.text_content()), None)
        
        if nome_index is None:
            continue
        
        # 4. Extração dos nomes dos alunos
        for row in rows[header_index + 1:]:
            row_text = row.text_content().strip()
            if "Total de Matrículas" in row_text or "Turma:" in row_text:
                break
            
            cells = row.xpath(".//td")
            if len(cells) > nome_index:
                student_name = cells[nome_index].text_content().strip()
                # Valida se o nome contém caracteres alfabéticos (evita linhas vazias ou numéricas)
                if student_name and re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', student_name):
                    classes[current_turma].append(student_name)
    
    # Fallback para nome da unidade via nome do arquivo
    if not unidade_name and filename:
        unidade_name = os.path.splitext(filename)[0]
    
    unidade_name = unidade_name or "Unidade não identificada"
    
    # Limpeza de caracteres inválidos para sistemas de arquivos e JSON
    unidade_name = re.sub(r'[\\/*?:"<>|]', '', unidade_name).strip()
    unidade_name = ' '.join(unidade_name.split())

    return {'schools': {unidade_name: classes}}