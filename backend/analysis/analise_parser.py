from lxml import html
from bs4 import BeautifulSoup
import re
import os
import logging
from .utils import setup_new_logger, get_month_name

# Configura o logger
logger = setup_new_logger()

# Módulo de análise de chamadas escolares
# Este arquivo incorpora as funções anteriormente em attendance_parser.py 
# combinadas com o algoritmo avançado de analise_parser.py

def is_elementary_education(class_name):
    """
    Determina se uma turma é de ensino fundamental (obrigatório) ou infantil (não obrigatório).
    """
    if not class_name:
        return False
    
    elementary_patterns = [
        r'\d+\s*[\u00ba\u00aa]\s*(ano|ANO)',  # 1º ano, 2ª ano, etc.
        r'^(EF\d|EM\d)',   # EF1, EF2, EM1, etc.
        r'^\d{1,2}\s*ANO'   # 1 ANO, 2 ANO, etc.
    ]
    
    return any(re.search(pattern, class_name, re.IGNORECASE) for pattern in elementary_patterns)

def get_education_type(class_name):
    """
    Determina o tipo de educação com base no nome da turma.
    """
    if not class_name:
        return "infantil"  # Padrão: infantil se não for possível determinar
    
    if is_elementary_education(class_name):
        return "fundamental"
    
    return "infantil"

def get_school_info(html_content):
    """
    Extrai informações básicas da escola e turma.
    Retorna um dicionário com as chaves:
    - unit_name: Nome da unidade escolar
    - class_name: Nome da turma
    - school_days: Número de dias letivos (default: 0)
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        info = {
            'unit_name': 'Não identificada',
            'class_name': 'Não identificada',
            'school_days': 0
        }
        
        # Método 1: Tenta extrair o nome da unidade escolar via títulos
        title_elements = soup.find_all(['title', 'h1', 'h2'])
        for title in title_elements:
            text = title.get_text().strip()
            if text and 'Turma:' not in text and 'Relatório' not in text:
                info['unit_name'] = text.split('-')[0].strip() if '-' in text else text
                logger.info(f"Unidade escolar encontrada (método 1): {info['unit_name']}")
                break
                
        # Método 2: Se não encontrou, busca em spans com texto que contenha CEI, CAIC, EBM, etc.
        if info['unit_name'] == 'Não identificada':
            school_prefixes = ['CEI', 'CAIC', 'EBM', 'ERM', 'EMEB', 'EM', 'ER', 'EI', 'GE', 'CRECHE', 'CENTRO', 'FUNDAÇÃO']
            for span in soup.find_all('span'):
                text = span.get_text().strip()
                if text and any(prefix in text.upper() for prefix in school_prefixes):
                    info['unit_name'] = text
                    logger.info(f"Unidade escolar encontrada (método 2): {info['unit_name']}")
                    break
                    
        # Método 3: Busca no primeiro texto em negrito e maiusculo
        if info['unit_name'] == 'Não identificada':
            for span in soup.find_all('span'):
                style = span.get('style', '')
                if 'font-weight: bold' in style:
                    text = span.get_text().strip()
                    if text and text.isupper() and len(text) > 4 and ' ' in text:
                        info['unit_name'] = text
                        logger.info(f"Unidade escolar encontrada (método 3): {info['unit_name']}")
                        break
        
        # Tenta extrair a turma
        turma_elements = soup.find_all(string=re.compile(r'Turma:'))
        if turma_elements:
            turma_text = turma_elements[0]
            # Expressão regular atualizada para capturar o nome completo da turma após "Turma:"
            # incluindo padrões como "X ANO - Y" (onde X e Y são números)
            match = re.search(r'Turma:\s*(\d+\s*[\u00ba\u00aa]*\s*ANO\s*-\s*\d+|[^(\n]+)', str(turma_text))
            if match:
                info['class_name'] = match.group(1).strip()
                logger.info(f"Turma encontrada: {info['class_name']}")
                
        # Segunda tentativa para turmas no formato X ANO - Y
        if 'Não identificada' in info['class_name'] or not info['class_name']:
            # Busca especificamente o padrão "X ANO - Y" em todo o documento
            ano_pattern = re.compile(r'\b(\d+\s*[\u00ba\u00aa]*\s*ANO\s*-\s*\d+)\b')
            matches = soup.find_all(string=ano_pattern)
            if matches:
                for match_text in matches:
                    result = ano_pattern.search(match_text)
                    if result:
                        info['class_name'] = result.group(1).strip()
                        logger.info(f"Turma encontrada (formato ANO): {info['class_name']}")
                        break
        
        # Se não encontrou via Turma:, tenta outros padrões
        if info['class_name'] == 'Não identificada':
            for span in soup.find_all('span'):
                text = span.get_text().strip()
                
                # Busca padrões específicos para capturar nome completo de turmas
                # GT4 A, GT 4 A, GT4A
                gt_match = re.search(r'GT\s*\d+\s*[A-Z]', text, re.IGNORECASE)
                if gt_match:
                    info['class_name'] = gt_match.group(0).strip()
                    logger.info(f"Turma GT encontrada: {info['class_name']}")
                    break
                    
                # 8º ANO - 1, 2º ANO 1, 3º A, 4º ANO - 1, etc.
                # Expressão regular melhorada para capturar o nome completo incluindo "ANO" seguido de número
                ano_match = re.search(r'\d+\s*º\s*(?:ANO)\s*(?:-\s*\d+|\s+\d+|\s+[A-Z])|\d+\s*º\s*[A-Z]', text, re.IGNORECASE)
                if ano_match:
                    info['class_name'] = ano_match.group(0).strip()
                    logger.info(f"Turma ANO encontrada: {info['class_name']}")
                    break
                    
                # Outros padrões como CAIC 4º ANO 1
                outros_match = re.search(r'[A-Z]+\s*\d+\s*º\s*(?:ANO)?\s*(?:-\s*\d+|\s+\d+)?', text, re.IGNORECASE)
                if outros_match:
                    info['class_name'] = outros_match.group(0).strip()
                    logger.info(f"Turma Outro encontrada: {info['class_name']}")
                    break
        
        # Extrai o número de dias letivos
        for span in soup.find_all('span'):
            text = span.get_text().strip()
            if 'TOTAL DIAS LETIVOS' in text.upper():
                # Procura números na mesma ou próxima célula
                match = re.search(r'(\d+)', text)
                if match:
                    info['school_days'] = int(match.group(1))
                    logger.info(f"Dias letivos: {info['school_days']}")
                    break
                
                # Verifica a célula seguinte
                cell = span.find_parent('td')
                if cell:
                    next_cell = cell.find_next_sibling('td')
                    if next_cell:
                        next_text = next_cell.get_text().strip()
                        match = re.search(r'(\d+)', next_text)
                        if match:
                            info['school_days'] = int(match.group(1))
                            logger.info(f"Dias letivos (célula próxima): {info['school_days']}")
                            break
                
        return info
    except Exception as e:
        logger.error(f"Erro ao extrair informações da escola: {e}")
        return {'unit_name': 'Não identificada', 'class_name': 'Não identificada', 'school_days': 0}

def get_student_list(html_content):
    """
    Extrai a lista completa de alunos do documento.
    Usa múltiplos métodos para garantir que encontre os alunos em diferentes formatos de página.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        students = []
        
        # Método 1: Procura por células que contêm nomes de alunos em tabelas com 'Nome'
        headers = soup.find_all(text=re.compile(r'Nome'))
        for header in headers:
            header_cell = header.find_parent(['th', 'td'])
            if header_cell:
                table = header_cell.find_parent('table')
                if table:
                    rows = table.find_all('tr')
                    col_idx = None
                    
                    # Encontra o índice da coluna do nome
                    for idx, cell in enumerate(header_cell.find_parent('tr').find_all(['th', 'td'])):
                        if 'Nome' in cell.get_text():
                            col_idx = idx
                            break
                    
                    if col_idx is not None:
                        # Extrai os nomes dos alunos
                        for row in rows:
                            cells = row.find_all(['th', 'td'])
                            if len(cells) > col_idx:
                                name = cells[col_idx].get_text().strip()
                                if name and name != 'Nome' and re.search(r'[a-zA-Z]', name):
                                    students.append(name)
                                    logger.debug(f"Aluno encontrado (método 1): {name}")
        
        # Método 2: Procura spans com fonte pequena (7px) em maiúscula (estilo do direct_parser)
        if not students:
            logger.info(f"Tentando método 2 para extrair nomes dos alunos")
            for span in soup.find_all('span'):
                style = span.get('style', '')
                if 'font-size: 7px' in style:
                    text = span.get_text().strip()
                    # Nomes de alunos são tipicamente maiúsculos, contêm espaços e letras
                    if (len(text) > 5 and ' ' in text and text.isupper() and 
                        any(c.isalpha() for c in text) and 
                        not text.startswith('TOTAL') and 'DIAS LETIVOS' not in text.upper()):
                        # Normaliza o nome (remove espaços extras)
                        student_name = ' '.join(text.split())
                        students.append(student_name)
                        logger.debug(f"Aluno encontrado (método 2): {student_name}")
        
        # Método 3: Procura em qualquer célula TD com texto em maiúsculas
        if not students:
            logger.info(f"Tentando método 3 para extrair nomes dos alunos")
            for td in soup.find_all('td'):
                text = td.get_text().strip()
                # Verifica se parece um nome de aluno (maiúsculas, palavras múltiplas, sem números)
                if (len(text) > 8 and ' ' in text and text.isupper() and 
                    all(not c.isdigit() for c in text) and
                    not text.startswith('TOTAL') and 'DIAS LETIVOS' not in text.upper()):
                    student_name = ' '.join(text.split())
                    students.append(student_name)
                    logger.debug(f"Aluno encontrado (método 3): {student_name}")
        
        # Método 4: usar as tabelas com marcações F, FJ, P
        if not students:
            logger.info(f"Tentando método 4 para extrair nomes dos alunos")
            for span in soup.find_all('span'):
                # Procura por spans com marcações de presença/faltas (fonte 6px e bold)
                style = span.get('style', '')
                if 'font-size: 6px' in style and 'font-weight: bold' in style:
                    text = span.get_text().strip()
                    if text in ['.', 'F', 'FJ']:  # Marcações válidas
                        # Pega o pai (td) e seus atributos para identificar a célula
                        td = span.find_parent('td')
                        if td:
                            # Pega o pai (tr) que contém informações sobre o aluno
                            tr = td.find_parent('tr')
                            if tr:
                                # Tenta encontrar um nome de aluno na mesma linha
                                student_spans = tr.find_all('span', {'style': lambda s: s and 'font-size: 7px' in s})
                                for student_span in student_spans:
                                    name_text = student_span.get_text().strip()
                                    if (len(name_text) > 5 and ' ' in name_text and name_text.isupper() and 
                                        any(c.isalpha() for c in name_text)):
                                        student_name = ' '.join(name_text.split())
                                        students.append(student_name)
                                        logger.debug(f"Aluno encontrado (método 4): {student_name}")
                                        break
        
        # Remove possíveis duplicatas e ordena
        unique_students = sorted(set(students))
        logger.info(f"Total de alunos encontrados: {len(unique_students)}")
        return unique_students
    except Exception as e:
        logger.error(f"Erro ao extrair lista de alunos: {e}")
        logger.exception("Detalhes do erro:")
        return []

def find_date_columns(soup):
    """
    Identifica todas as colunas que contêm datas no formato DD/MM.
    """
    date_columns = []
    date_pattern = re.compile(r'\d{2}/\d{2}')
    
    # Procura datas nas células de cabeçalho
    headers = soup.find_all(['th', 'td'])
    for header in headers:
        text = header.get_text().strip()
        if date_pattern.match(text):
            date_columns.append({
                'text': text,
                'element': header,
                'month': int(text.split('/')[1])
            })
    
    return date_columns

def is_f_mark(cell):
    """
    Verifica se uma célula contém uma marcação 'F'.
    """
    text = cell.get_text().strip().upper()
    return text == 'F'

def is_yellow_cell(cell):
    """
    Verifica se uma célula tem fundo amarelo (aula não ministrada).
    """
    style = cell.get('style', '')
    return 'background-color:yellow' in style.lower() or 'background-color: yellow' in style.lower()

def process_student_attendance(html_content, student_name):
    """
    Processa as faltas de um aluno específico seguindo exatamente o passo a passo.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Localiza o nome do aluno nas tabelas
        student_cells = soup.find_all(text=lambda text: text and student_name in str(text))
        student_rows = [cell.find_parent('tr') for cell in student_cells if cell and cell.find_parent('tr')]
        
        logger.info(f"Localizou {len(student_rows)} linhas para o aluno {student_name}")
        
        # 2. Identifica as colunas com datas
        date_columns = find_date_columns(soup)
        logger.info(f"Encontrou {len(date_columns)} colunas de datas no documento")
        
        # Método alternativo: busca diretamente por todas as células com 'F' no documento
        # e verifica nas colunas correspondentes se são datas
        all_f_marks = soup.find_all('span', string='F')
        logger.info(f"Encontrou {len(all_f_marks)} marcações 'F' no documento")
        
        # 3. Inicializa o contador de faltas por mês
        faltas_por_mes = {}
        
        # Método 1: Processa as faltas diretamente a partir da matriz de chamada
        for f_mark in all_f_marks:
            # Encontra a célula onde está o 'F'
            f_cell = f_mark.find_parent('td')
            if not f_cell or is_yellow_cell(f_cell):
                continue
                
            # Encontra a linha dessa célula
            f_row = f_cell.find_parent('tr')
            if not f_row:
                continue
                
            # Verifica se essa linha pertence ao aluno desejado
            row_text = f_row.get_text()
            if student_name not in row_text:
                continue
                
            logger.info(f"Encontrou marcação F para o aluno {student_name}")
            
            # Encontra a tabela e as datas nos cabeçalhos
            table = f_row.find_parent('table')
            if not table:
                continue
                
            # Encontra o índice dessa célula
            f_idx = None
            row_cells = f_row.find_all(['td', 'th'])
            for idx, cell in enumerate(row_cells):
                if cell == f_cell:
                    f_idx = idx
                    break
                    
            if f_idx is None:
                continue
                
            # Busca a data correspondente nos cabeçalhos
            header_rows = table.find_all('tr')
            date_found = False
            
            for hrow in header_rows:
                header_cells = hrow.find_all(['th', 'td'])
                if len(header_cells) <= f_idx:
                    continue
                    
                header_text = header_cells[f_idx].get_text().strip()
                date_match = re.match(r'(\d{2})/(\d{2})', header_text)
                
                if date_match:
                    day, month = date_match.groups()
                    month = int(month)
                    logger.info(f"Data associada à falta: {day}/{month}")
                    
                    if month not in faltas_por_mes:
                        faltas_por_mes[month] = 0
                    faltas_por_mes[month] += 1
                    date_found = True
                    break
                    
            if date_found:
                continue
                
        # Método 2 (original): Para cada linha do aluno, processa as marcações de falta
        if not faltas_por_mes:  # Se o método 1 não encontrou nada, tenta o método 2
            logger.info(f"Método 1 não encontrou faltas, tentando método 2")
            for row in student_rows:
                if not row:
                    continue
                    
                cells = row.find_all(['td', 'th'])
                student_idx = None
                
                # Encontra o índice da célula que contém o nome do aluno
                for idx, cell in enumerate(cells):
                    if student_name in cell.get_text():
                        student_idx = idx
                        break
                
                if student_idx is None:
                    continue
                
                # Percorre a mesma tabela para encontrar cabeçalhos com datas
                table = row.find_parent('table')
                if not table:
                    continue
                    
                header_rows = table.find_all('tr')
                header_cells = None
                
                for hrow in header_rows:
                    header_texts = [cell.get_text().strip() for cell in hrow.find_all(['th', 'td'])]
                    if any(re.match(r'\d{2}/\d{2}', text) for text in header_texts):
                        header_cells = hrow.find_all(['th', 'td'])
                        break
                
                if not header_cells:
                    continue
                    
                # Analisa cada célula na linha do aluno e correlaciona com as datas
                for idx, cell in enumerate(cells):
                    if idx >= len(header_cells):
                        continue
                        
                    header_text = header_cells[idx].get_text().strip()
                    date_match = re.match(r'(\d{2})/(\d{2})', header_text)
                    
                    if date_match and is_f_mark(cell) and not is_yellow_cell(cell):
                        day, month = date_match.groups()
                        month = int(month)
                        logger.info(f"Data associada à falta (método 2): {day}/{month}")
                        
                        if month not in faltas_por_mes:
                            faltas_por_mes[month] = 0
                        faltas_por_mes[month] += 1
        
        # Converte para formato textual
        faltas_texto = []
        for month in sorted(faltas_por_mes.keys()):
            month_name = get_month_name(month)  # Converte para abreviação do mês em português
            faltas_texto.append(f"{month_name}: {faltas_por_mes[month]}")
        
        return {
            'faltas_por_mes': faltas_por_mes,
            'faltas_por_mes_texto': ", ".join(faltas_texto),
            'maior_falta_mensal': max(faltas_por_mes.values()) if faltas_por_mes else 0
        }
    except Exception as e:
        logger.error(f"Erro ao processar frequência do aluno {student_name}: {e}")
        return {
            'faltas_por_mes': {},
            'faltas_por_mes_texto': "",
            'maior_falta_mensal': 0
        }

def get_pages(soup):
    """
    Divide o documento em páginas individuais.
    """
    pages = []
    page_tables = soup.find_all('table', class_='jrPage')
    
    for table in page_tables:
        pages.append(table)
    
    return pages

def find_student_row(page_soup, student_name):
    """
    Encontra a linha (TR) onde aparece o nome do aluno.
    """
    student_cells = page_soup.find_all(text=lambda text: text and student_name in str(text))
    for cell in student_cells:
        row = cell.find_parent('tr')
        if row:
            return row
    return None

def find_totals_in_html(html_content, student_name):
    """
    Busca os totais de P, F e FJ para um aluno específico.
    
    Esta implementação utiliza uma abordagem direta e consistente para todos os alunos.
    Busca especificamente em todas as tabelas de totais com as colunas P, F e FJ identificadas,
    incluindo quando os totais estão divididos em múltiplas páginas.
    
    Args:
        html_content (str): Conteúdo HTML completo
        student_name (str): Nome do aluno para buscar os totais
        
    Returns:
        dict: Dicionário com os valores de P, F e FJ encontrados
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        totals = {'P': 0, 'F': 0, 'FJ': 0}
        
        # Define os padrões de busca que cobrem diferentes formatos de tabela
        total_patterns = {
            'tabela': [
                # Busca tabelas com totais explicitamente rotulados
                {'header': re.compile(r'Total P', re.IGNORECASE), 'key': 'P'},
                {'header': re.compile(r'Total F', re.IGNORECASE), 'key': 'F'},
                {'header': re.compile(r'Total FJ', re.IGNORECASE), 'key': 'FJ'},
                # Busca cabeçalhos simples P/F/FJ
                {'header': re.compile(r'^P$', re.IGNORECASE), 'key': 'P'},
                {'header': re.compile(r'^F$', re.IGNORECASE), 'key': 'F'},
                {'header': re.compile(r'^FJ$', re.IGNORECASE), 'key': 'FJ'},
            ],
            'linha': [
                # Busca textos em linhas com os rótulos P/F/FJ
                {'label': re.compile(r'\bP\b', re.IGNORECASE), 'key': 'P'},
                {'label': re.compile(r'\bF\b', re.IGNORECASE), 'key': 'F'},
                {'label': re.compile(r'\bFJ\b', re.IGNORECASE), 'key': 'FJ'},
                # Busca textos explícitos de presença/falta
                {'label': re.compile(r'Presen[\u00e7c][\u00e7c]a', re.IGNORECASE), 'key': 'P'},
                {'label': re.compile(r'Falta', re.IGNORECASE), 'key': 'F'},
                {'label': re.compile(r'Falta Justificada', re.IGNORECASE), 'key': 'FJ'},
            ]
        }
        
        # Localiza todas as páginas/tabelas no documento
        pages = soup.find_all('table', class_='jrPage')
        if not pages:  # Fallback para qualquer tabela se não houver tabelas de página
            pages = soup.find_all('table')
        
        # Verifica todas as tabelas do documento
        for page in pages:
            # Procura o aluno na tabela atual
            student_row = None
            rows = page.find_all('tr')
            
            # Encontra a linha do aluno
            for row in rows:
                row_text = row.get_text()
                if student_name in row_text:
                    # Confirma que é uma linha com dados e não um cabeçalho
                    if any(c.get_text().strip().isdigit() for c in row.find_all(['td', 'th'])):
                        student_row = row
                        break
            
            if not student_row:
                continue  # Sem aluno nesta tabela, vamos para a próxima
            
            # Primeiro método: Busca por cabeçalhos de colunas P/F/FJ
            header_row = None
            
            # Procura pelo cabeçalho acima da linha do aluno
            for row in rows:
                if row == student_row:
                    break
                    
                for pattern in total_patterns['tabela']:
                    for cell in row.find_all(['th', 'td']):
                        text = cell.get_text().strip()
                        if pattern['header'].search(text):
                            header_row = row
                            break
                    if header_row:
                        break
                if header_row:
                    break
            
            # Se encontrou um cabeçalho, extrai os valores correspondentes
            if header_row:
                header_cells = header_row.find_all(['th', 'td'])
                student_cells = student_row.find_all(['th', 'td'])
                
                # Coordena as colunas entre o cabeçalho e os valores
                for i, header_cell in enumerate(header_cells):
                    if i < len(student_cells):
                        header_text = header_cell.get_text().strip()
                        student_text = student_cells[i].get_text().strip()
                        
                        # Verifica se o valor do aluno é um número e associa ao tipo correto
                        if student_text.isdigit():
                            for pattern in total_patterns['tabela']:
                                if pattern['header'].search(header_text):
                                    totals[pattern['key']] = int(student_text)
                                    break
            else:
                # Segundo método: Busca diretamente na linha do aluno por padrões P/F/FJ seguidos de números
                row_text = student_row.get_text()
                for pattern in total_patterns['linha']:
                    matches = list(pattern['label'].finditer(row_text))
                    for match in matches:
                        # Procura um número após o rótulo
                        end_pos = match.end()
                        number_match = re.search(r'\d+', row_text[end_pos:end_pos+10])
                        if number_match:
                            totals[pattern['key']] = int(number_match.group())
                
                # Terceiro método: Verifica se há três números consecutivos que podem ser P, F, FJ
                cells = student_row.find_all(['td', 'th'])
                digit_cells = [cell for cell in cells if cell.get_text().strip().isdigit()]
                
                if len(digit_cells) >= 3:
                    # Assume que os últimos três números são P, F, FJ na ordem
                    last_three = digit_cells[-3:]
                    if all(c.get_text().strip().isdigit() for c in last_three):
                        totals['P'] = int(last_three[0].get_text().strip())
                        totals['F'] = int(last_three[1].get_text().strip())
                        totals['FJ'] = int(last_three[2].get_text().strip())
        
        return totals
    except Exception as e:
        logger.error(f"Erro ao buscar totais para {student_name}: {e}")
        return {'P': 0, 'F': 0, 'FJ': 0}

def analyze_elementary_file(html_content):
    """
    Analisa um arquivo HTML de ensino fundamental seguindo o algoritmo passo a passo.
    Retorna o formato esperado pelo módulo original direct_parser.
    """
    try:
        # 1. Extrai informações básicas
        info = get_school_info(html_content)
        
        # 2. Extrai a lista de alunos
        students = get_student_list(html_content)
        
        # 3. Determina o tipo de educação
        education_type = get_education_type(info['class_name'])
        
        # 4. Prepara o resultado final no formato esperado pelo direct_parser
        result = {
            'class_name': info['class_name'],
            'school_name': info['unit_name'],
            'education_type': education_type,
            'students': []
        }
        
        # 5. Processa cada aluno
        for student_name in students:
            # 5.1. Extrai totais do aluno
            totals = find_totals_in_html(html_content, student_name)
            
            # 5.2. Processa as faltas por mês
            attendance = process_student_attendance(html_content, student_name)
            logger.info(f"Processando faltas por mês para {student_name}: {attendance.get('faltas_por_mes', {})}")
            logger.info(f"Texto de faltas por mês: {attendance.get('faltas_por_mes_texto', '')}")
            if not attendance.get('faltas_por_mes'):
                logger.warning(f"Método tradicional não encontrou faltas. Tentando método alternativo...")
                
                # Implementa extração direta de F por mês
                soup = BeautifulSoup(html_content, 'html.parser')
                faltas_por_mes = {}
                
                # Busca todas as marcações F no documento
                f_marks = soup.find_all('span', string='F')
                logger.info(f"Encontradas {len(f_marks)} marcações F no documento")
                
                # Para cada F, verifica se é do aluno atual e extrai o mês
                for f_mark in f_marks:
                    cell = f_mark.find_parent('td')
                    if not cell or is_yellow_cell(cell):
                        continue
                        
                    row = cell.find_parent('tr')
                    if not row or student_name not in row.get_text():
                        continue
                    
                    logger.info(f"Encontrada marcação F para {student_name}")
                    
                    # Determina o índice da célula com F
                    cells = row.find_all('td')
                    cell_idx = None
                    for idx, c in enumerate(cells):
                        if c == cell:
                            cell_idx = idx
                            break
                    
                    if cell_idx is None:
                        continue
                    
                    # Busca o cabeçalho de data para esta célula
                    table = row.find_parent('table')
                    if not table:
                        continue
                        
                    # Procura em todas as linhas por um cabeçalho com data
                    for header_row in table.find_all('tr'):
                        header_cells = header_row.find_all(['th', 'td'])
                        if len(header_cells) <= cell_idx:
                            continue
                            
                        header_text = header_cells[cell_idx].get_text().strip()
                        date_match = re.search(r'(\d{2})/(\d{2})', header_text)
                        
                        if date_match:
                            day, month = date_match.groups()
                            month = int(month)
                            logger.info(f"Encontrada falta em {day}/{month}")
                            
                            if month not in faltas_por_mes:
                                faltas_por_mes[month] = 0
                            faltas_por_mes[month] += 1
                            break
                
                # Se encontrou faltas com o método alternativo, atualiza attendance
                if faltas_por_mes:
                    faltas_texto = []
                    for month in sorted(faltas_por_mes.keys()):
                        month_name = get_month_name(month)
                        faltas_texto.append(f"{month_name}: {faltas_por_mes[month]}")
                    
                    attendance = {
                        'faltas_por_mes': faltas_por_mes,
                        'faltas_por_mes_texto': ", ".join(faltas_texto),
                        'maior_falta_mensal': max(faltas_por_mes.values()) if faltas_por_mes else 0
                    }
                    logger.info(f"Método alternativo encontrou faltas: {attendance['faltas_por_mes_texto']}")
                    logger.info(f"Maior falta mensal: {attendance['maior_falta_mensal']}")
            elif attendance.get('faltas_por_mes'):
                logger.info(f"Maior falta mensal detectada: {attendance.get('maior_falta_mensal', 0)}")
            else:
                logger.warning(f"Nenhum método conseguiu encontrar faltas por mês para {student_name}")
            
            # 5.3. Cria o dicionário de dados do aluno (compatibilidade com direct_parser)
            student_data = {
                'aluno': student_name,  # Campo 'aluno' é usado pelo rules_engine
                'name': student_name,  # Campo 'name' usado em alguns lugares
                'P': totals.get('P', 0),
                'F': totals.get('F', 0),
                'FJ': totals.get('FJ', 0),
                'unidade': info['unit_name'],
                'escola': info['unit_name'],  # Manter compatibilidade
                'turma': info['class_name'],
                'dias_letivos': info.get('school_days', 0),
                'faltas_por_mes': attendance.get('faltas_por_mes', {}),
                'maior_falta_mensal': attendance.get('maior_falta_mensal', 0),
                'faltas_por_mes_texto': attendance.get('faltas_por_mes_texto', '')
            }
            
            # 5.4. Calcula as estatísticas
            total_aulas = totals.get('P', 0) + totals.get('F', 0) + totals.get('FJ', 0)
            if total_aulas > 0:
                student_data['percentual_presenca'] = round((totals.get('P', 0) / total_aulas) * 100, 1)
            else:
                student_data['percentual_presenca'] = 0
                
            # 5.5. Adiciona porcentagem de faltas justificadas
            total_faltas = totals.get('F', 0) + totals.get('FJ', 0)
            if total_faltas > 0:
                student_data['percentual_justificado'] = round((totals.get('FJ', 0) / total_faltas) * 100, 1)
            else:
                student_data['percentual_justificado'] = 0
            
            result['students'].append(student_data)
        
        logger.info(f"Processamento concluído. {len(result['students'])} alunos processados.")
        return result
        
    except Exception as e:
        logger.error(f"Erro ao analisar arquivo: {e}")
        logger.exception("Detalhes do erro:")
        return {
            'class_name': None,
            'school_name': None,
            'education_type': 'infantil',
            'students': []
        }

# Função compatível com o nome usado em direct_parser.py
def analyze_attendance_html(html_content):
    """
    Função wrapper para compatibilidade com a interface original.
    """
    return analyze_elementary_file(html_content)