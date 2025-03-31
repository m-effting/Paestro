from lxml import html
import re
import os


def parse_html_content(html_content, filename=None):
    """
    Extrai turmas, alunos e nome da unidade de relatórios HTML escolares.
    
    Fluxo principal:
    1. Pré-processa HTML e verifica validade
    2. Extrai nome da unidade (3 tentativas em ordem):
       - Tags comuns (título, cabeçalhos)
       - Linha da turma (suporta parênteses não fechados)
       - Nome do arquivo (fallback)
    3. Processa tabelas para extrair:
       - Nomes das turmas (formato "X ANO - Y")
       - Listas de alunos por turma
    4. Padroniza nome da unidade (remove caracteres inválidos, espaços extras)

    Args:
        html_content: String com conteúdo HTML
        filename: Nome do arquivo de origem (opcional)

    Returns:
        (dict, str): 
        - Dicionário {turma: [alunos]}
        - Nome formatado da unidade escolar
    """
    
    # Verificação inicial do input
    if not html_content or not isinstance(html_content, (str, bytes)):
        return {}, os.path.splitext(filename)[0] if filename else "Unidade não identificada"

    try:
        tree = html.fromstring(html_content)
    except Exception as e:
        return {}, os.path.splitext(filename)[0] if filename else "Unidade não identificada"

    classes = {}
    current_turma = None
    unidade_name = None
    
    # Expressão regular melhorada para capturar nomes com parênteses não fechados
    TURMA_REGEX = re.compile(
        r'Turma:\s*([^(\n]+)\s*(?:\(([^)\n]+)|$)',
        re.UNICODE
    )
    
    # 1. Primeira tentativa: Extrai de tags comuns (título, cabeçalhos)
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
                # Remove hífens no final e limpa espaços
                unidade_name = re.sub(r'-\s*$', '', text.split('-')[0] if '-' in text else text).strip()
                break

    tables = tree.xpath("//table[contains(@class, 'jrPage')]")
    
    for table in tables:
        rows = table.xpath(".//tr")
        turma_row = None
        
        # Procura pela linha que contém a turma
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
                
                # 2. Segunda tentativa: Extrai nome da unidade dos parênteses (mesmo não fechados)
                if match.group(2):
                    unidade_candidate = match.group(2).strip()
                    # Remove hífens no final e limpa espaços
                    unidade_candidate = re.sub(r'-\s*$', '', unidade_candidate).strip()
                    if unidade_candidate and not unidade_name:
                        unidade_name = unidade_candidate
                
                if current_turma not in classes:
                    classes[current_turma] = []
        
        if not current_turma:
            continue
        
        # Processamento dos alunos...
        header_row = None
        header_index = None
        for idx, row in enumerate(rows):
            text = row.text_content().strip()
            if "Código" in text and "Nome" in text:
                header_row = row
                header_index = idx
                break
        
        if header_row is None or header_index is None:
            continue
        
        header_cells = header_row.xpath(".//th") or header_row.xpath(".//td")
        nome_index = None
        for i, cell in enumerate(header_cells):
            if "Nome" in cell.text_content():
                nome_index = i
                break
        
        if nome_index is None:
            continue
        
        students = []
        for row in rows[header_index + 1:]:
            row_text = row.text_content().strip()
            if "Total de Matrículas" in row_text or "Turma:" in row_text:
                break
            cells = row.xpath(".//td")
            if len(cells) > nome_index:
                student_name = cells[nome_index].text_content().strip()
                if student_name and re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', student_name):
                    students.append(student_name)
        
        classes[current_turma].extend(students)
    
    # 3. Fallback: Usa nome do arquivo (sem extensão) se não encontrou no HTML
    if not unidade_name and filename:
        unidade_name = os.path.splitext(filename)[0]
    
    # Garante que temos um nome válido
    if not unidade_name:
        unidade_name = "Unidade não identificada"
    else:
        # Limpeza final do nome (remove apenas caracteres problemáticos para arquivos)
        unidade_name = re.sub(r'[\\/*?:"<>|]', '', unidade_name).strip()
        unidade_name = ' '.join(unidade_name.split())

    return classes, unidade_name