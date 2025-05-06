import re
import logging
from bs4 import BeautifulSoup
from collections import defaultdict
from .utils import get_month_name
from .find_totals import find_totals_in_html

# Configuração de log
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s [%(levelname)-5s] [%(name)-15s] %(funcName)-15s – %(message)s',
                    filename='attendance_parser.log',
                    filemode='w')

logger = logging.getLogger('direct_parser')

# Mapeamento dos números de mês para seus nomes abreviados em português
MONTH_NAMES = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 
              7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}

def extract_basic_info(html_content):
    """Extrai informações básicas do documento HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        'school_name': None,
        'class_name': None,
        'school_days': None
    }
    
    # Extrai o nome da escola
    school_prefixes = ['CEI', 'CAIC', 'EBM', 'ERM', 'EMEB', 'EM', 'ER', 'EI', 'GE',
                     'CRECHE', 'CENTRO', 'FUNDAÇÃO']
    
    for span in soup.find_all('span'):
        text = span.get_text().strip()
        for prefix in school_prefixes:
            if text.startswith(prefix) and len(text) > len(prefix):
                result['school_name'] = text
                logger.info(f"Escola: {text}")
                break
        if result['school_name']:
            break
    
    # Extrai o nome da turma
    for span in soup.find_all('span'):
        text = span.get_text().strip()
        # Procura por padrões de nomes de turma
        if 'TURMA:' in text:
            # Pega todo o texto após "TURMA:" para capturar o nome completo da turma
            match = re.search(r'TURMA:\s*(.+)', text)
            if match:
                turma_completa = match.group(1).strip()
                
                # Verifica especificamente padrões de turmas infantis "GT X Y"
                gt_match = re.search(r'GT\s*([0-5])\s*([A-Z])', turma_completa, re.IGNORECASE)
                if gt_match:
                    # Normaliza para o formato "GT X Y" com espaços
                    gt_num = gt_match.group(1)
                    gt_letter = gt_match.group(2).upper()
                    result['class_name'] = f"GT {gt_num} {gt_letter}"
                    logger.info(f"Turma infantil encontrada: {result['class_name']}")
                else:
                    result['class_name'] = turma_completa
                    logger.info(f"Turma completa: {result['class_name']}")
                break
    
    # Se não encontrou via TURMA:, tenta outros padrões
    if not result['class_name']:
        for span in soup.find_all('span'):
            text = span.get_text().strip()
            
            # Busca padrões mais abrangentes e específicos para capturar nome completo de turmas
            # GT4 A, GT 4 A, GT4A, GT 4A, etc (turmas infantis)
            gt_match = re.search(r'GT\s*([0-5])\s*([A-Z])', text, re.IGNORECASE)
            if gt_match:
                # Normaliza para o formato "GT X Y" com espaços
                gt_num = gt_match.group(1)
                gt_letter = gt_match.group(2).upper()
                result['class_name'] = f"GT {gt_num} {gt_letter}"
                logger.info(f"Turma GT: {result['class_name']}")
                break
                
            # 8º ANO - 1, 2º ANO 1, 3º A, 4º ANO - 1, etc.
            # Expressão regular melhorada para capturar o nome completo incluindo "ANO" seguido de número
            ano_match = re.search(r'\d+\s*º\s*(?:ANO)\s*(?:-\s*\d+|\s+\d+|\s+[A-Z])|\d+\s*º\s*[A-Z]', text, re.IGNORECASE)
            if ano_match:
                result['class_name'] = ano_match.group(0).strip()
                logger.info(f"Turma ANO: {result['class_name']}")
                break
                
            # Outros padrões como CAIC 4º ANO 1
            outros_match = re.search(r'[A-Z]+\s*\d+\s*º\s*(?:ANO)?\s*(?:-\s*\d+|\s+\d+)?', text, re.IGNORECASE)
            if outros_match:
                result['class_name'] = outros_match.group(0).strip()
                logger.info(f"Turma Outro: {result['class_name']}")
                break
    
    # Extrai o número de dias letivos
    for span in soup.find_all('span'):
        text = span.get_text().strip()
        if 'TOTAL DIAS LETIVOS' in text.upper():
            # Procura números na mesma ou próxima célula
            match = re.search(r'(\d+)', text)
            if match:
                result['school_days'] = int(match.group(1))
                logger.info(f"Dias letivos: {result['school_days']}")
                break
            
            # Verifica a célula seguinte
            cell = span.find_parent('td')
            if cell:
                next_cell = cell.find_next_sibling('td')
                if next_cell:
                    next_text = next_cell.get_text().strip()
                    match = re.search(r'(\d+)', next_text)
                    if match:
                        result['school_days'] = int(match.group(1))
                        logger.info(f"Dias letivos (célula próxima): {result['school_days']}")
                        break
    
    return result

def extract_dates(soup):
    """Extrai todas as datas do documento no formato DD/MM."""
    dates = []
    months_found = set()
    date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})')
    
    for span in soup.find_all('span'):
        text = span.get_text().strip()
        match = date_pattern.search(text)
        if match and len(text) <= 6:  # Limita o tamanho para evitar textos longos com datas
            day = int(match.group(1))
            month = int(match.group(2))
            if 1 <= day <= 31 and 1 <= month <= 12:
                dates.append({'day': day, 'month': month, 'text': text})
                months_found.add(month)
                logger.debug(f"Data encontrada: {day}/{month}")
    
    # Ordena por mês para facilitar a análise
    dates_by_month = {}
    for month in sorted(months_found):
        month_dates = [date for date in dates if date['month'] == month]
        dates_by_month[month] = month_dates
        month_name = MONTH_NAMES.get(month, f"Mês {month}")
        logger.info(f"Mês {month} ({month_name}): {len(month_dates)} datas")
    
    return dates, dates_by_month, months_found

def extract_students(soup):
    """Extrai a lista de alunos do documento."""
    students = []
    
    # Procura spans com fonte pequena (7px ou 6px) e em maiúscula
    for span in soup.find_all('span'):
        style = span.get('style', '')
        if 'font-size: 7px' in style:
            text = span.get_text().strip()
            # Nomes de alunos são tipicamente maiúsculos, contém espaços e letras
            if (len(text) > 5 and ' ' in text and text.isupper() and 
                any(c.isalpha() for c in text) and 
                not text.startswith('TOTAL') and 'DIAS LETIVOS' not in text.upper()):
                # Normaliza o nome (remove espaços extras)
                student_name = ' '.join(text.split())
                students.append(student_name)
                logger.debug(f"Aluno encontrado: {student_name}")
    
    # Remove possíveis duplicatas e ordena
    unique_students = sorted(set(students))
    logger.info(f"Total de alunos encontrados: {len(unique_students)}")
    return unique_students

def extract_attendance_values(soup):
    """Extrai todas as marcações de presença e falta ('F', 'FJ', '.')."""
    attendance_marks = []
    
    # Procura por spans com marcações de presença/faltas (fonte 6px e bold)
    for span in soup.find_all('span'):
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
                        student_name = None
                        for student_span in student_spans:
                            name_text = student_span.get_text().strip()
                            if (len(name_text) > 5 and ' ' in name_text and name_text.isupper() and 
                                any(c.isalpha() for c in name_text)):
                                student_name = ' '.join(name_text.split())
                                break
                        
                        # Se não encontrou na linha atual, procura na linha anterior
                        if not student_name:
                            # Pega todas as linhas anteriores até encontrar um aluno
                            prev_lines = []
                            prev_tr = tr.find_previous_sibling('tr')
                            while prev_tr and not student_name and len(prev_lines) < 5:
                                prev_lines.append(prev_tr)
                                student_spans = prev_tr.find_all('span', {'style': lambda s: s and 'font-size: 7px' in s})
                                for student_span in student_spans:
                                    name_text = student_span.get_text().strip()
                                    if (len(name_text) > 5 and ' ' in name_text and name_text.isupper() and 
                                        any(c.isalpha() for c in name_text)):
                                        student_name = ' '.join(name_text.split())
                                        break
                                prev_tr = prev_tr.find_previous_sibling('tr')
                        
                        # Agora procura uma data na mesma coluna (mesma posição/índice)
                        date_info = None
                        if student_name:
                            # Encontre o índice desta célula na linha
                            all_cells = tr.find_all('td')
                            cell_idx = list(all_cells).index(td) if td in all_cells else -1
                            
                            # Procura datas em toda a tabela, em outras linhas, na mesma coluna
                            if cell_idx >= 0:
                                table = tr.find_parent('table')
                                if table:
                                    for header_tr in table.find_all('tr'):
                                        if header_tr == tr:
                                            continue  # Ignora a linha atual
                                        
                                        header_cells = header_tr.find_all('td')
                                        if cell_idx < len(header_cells):
                                            header_td = header_cells[cell_idx]
                                            date_text = header_td.get_text().strip()
                                            date_match = re.search(r'(\d{1,2})/(\d{1,2})', date_text)
                                            if date_match and len(date_text) <= 6:
                                                day = int(date_match.group(1))
                                                month = int(date_match.group(2))
                                                if 1 <= day <= 31 and 1 <= month <= 12:
                                                    date_info = {'day': day, 'month': month}
                                                    break
                            
                            # Adiciona a marcação com as informações do aluno e data
                            attendance_marks.append({
                                'mark': text,
                                'student': student_name,
                                'date': date_info
                            })
                            
                            if date_info:
                                logger.debug(f"Marcação: {text}, Aluno: {student_name}, Data: {date_info['day']}/{date_info['month']}")
                            else:
                                logger.debug(f"Marcação: {text}, Aluno: {student_name}, Data: [Não encontrada]")
    
    logger.info(f"Total de marcações extraídas: {len(attendance_marks)}")
    return attendance_marks

def extract_student_totals(soup, students):
    """Extrai os totais P, F, FJ para cada aluno."""
    totals = {}
    
    # Primeiro, tenta encontrar a tabela de totais que aparece no final do documento
    # ou a tabela que possui as colunas P, F, FJ juntas
    p_f_fj_table = None
    p_col_idx, f_col_idx, fj_col_idx = -1, -1, -1
    
    # Procura tabelas que podem conter os totais
    for table in soup.find_all('table'):
        # Verifica se esta tabela tem cabeçalhos P, F, FJ
        for tr in table.find_all('tr'):
            cells = tr.find_all('td')
            cell_texts = [cell.get_text().strip() for cell in cells]
            
            # Procura por um padrão onde 'P', 'F', 'FJ' aparecem próximos um do outro
            if 'P' in cell_texts and 'F' in cell_texts and 'FJ' in cell_texts:
                try:
                    p_col_idx = cell_texts.index('P')
                    f_col_idx = cell_texts.index('F')
                    fj_col_idx = cell_texts.index('FJ')
                    p_f_fj_table = table
                    logger.info(f"Encontrada tabela de totais com colunas P({p_col_idx}), F({f_col_idx}), FJ({fj_col_idx})")
                    break
                except ValueError:
                    # Se não conseguir encontrar algum dos índices, continua procurando
                    continue
        
        if p_f_fj_table:
            break
    
    # Se encontrou uma tabela com colunas P, F, FJ, extrai os valores para cada aluno
    if p_f_fj_table and p_col_idx >= 0 and f_col_idx >= 0 and fj_col_idx >= 0:
        logger.info("Usando tabela de totais encontrada")
        for student_name in students:
            student_totals = {'P': 0, 'F': 0, 'FJ': 0}
            
            # Procura a linha do aluno nesta tabela
            for tr in p_f_fj_table.find_all('tr'):
                tr_text = tr.get_text()
                if student_name in tr_text:
                    cells = tr.find_all('td')
                    
                    # Verifica se os índices estão dentro do range válido
                    if p_col_idx < len(cells):
                        p_text = cells[p_col_idx].get_text().strip()
                        if p_text.isdigit():
                            student_totals['P'] = int(p_text)
                    
                    if f_col_idx < len(cells):
                        f_text = cells[f_col_idx].get_text().strip()
                        if f_text.isdigit():
                            student_totals['F'] = int(f_text)
                    
                    if fj_col_idx < len(cells):
                        fj_text = cells[fj_col_idx].get_text().strip()
                        if fj_text.isdigit():
                            student_totals['FJ'] = int(fj_text)
                    
                    logger.info(f"Totais da tabela para {student_name}: P={student_totals['P']}, F={student_totals['F']}, FJ={student_totals['FJ']}")
                    break
            
            totals[student_name] = student_totals
        
        return totals
    
    # Se não encontrou uma tabela específica, procura os totais em cada linha de aluno
    logger.info("Buscando totais nas linhas de cada aluno")
    for student_name in students:
        student_totals = {'P': 0, 'F': 0, 'FJ': 0}
        student_found = False
        
        # Tenta identificar a última ocorrência do aluno (que geralmente contém os totais)
        last_tr_with_student = None
        for tr in soup.find_all('tr'):
            tr_text = tr.get_text().strip()
            if student_name in tr_text:
                last_tr_with_student = tr
        
        if last_tr_with_student:
            # Examina as células desta linha para encontrar números sequenciais
            cells = last_tr_with_student.find_all('td')
            digits_cells = []
            
            for cell in cells:
                cell_text = cell.get_text().strip()
                if cell_text.isdigit():
                    digits_cells.append((cell, int(cell_text)))
            
            # Procura três números sequenciais que possam ser P, F, FJ
            if len(digits_cells) >= 3:
                # Os totais geralmente são os últimos três números na linha
                # e geralmente seguem o padrão: P > F e P > FJ (presenças mais comuns que faltas)
                last_numbers = digits_cells[-3:]
                values = [value for _, value in last_numbers]
                
                # Tenta identificar qual é P, F e FJ com base na magnitude dos números
                if values[0] > values[1] and values[0] > values[2]:  # P deve ser o maior número
                    student_totals['P'] = values[0]
                    # Entre os dois restantes, o menor é tipicamente F e o maior é FJ
                    if values[1] < values[2]:
                        student_totals['F'] = values[1]
                        student_totals['FJ'] = values[2]
                    else:
                        student_totals['F'] = values[2]
                        student_totals['FJ'] = values[1]
                elif values[1] > values[0] and values[1] > values[2]:  # P é o segundo número
                    student_totals['P'] = values[1]
                    # Entre os dois restantes, o menor é tipicamente F e o maior é FJ
                    if values[0] < values[2]:
                        student_totals['F'] = values[0]
                        student_totals['FJ'] = values[2]
                    else:
                        student_totals['F'] = values[2]
                        student_totals['FJ'] = values[0]
                else:  # P é o terceiro número
                    student_totals['P'] = values[2]
                    # Entre os dois restantes, o menor é tipicamente F e o maior é FJ
                    if values[0] < values[1]:
                        student_totals['F'] = values[0]
                        student_totals['FJ'] = values[1]
                    else:
                        student_totals['F'] = values[1]
                        student_totals['FJ'] = values[0]
                
                student_found = True
                logger.info(f"Totais identificados para {student_name}: P={student_totals['P']}, F={student_totals['F']}, FJ={student_totals['FJ']}")
        
        # Se ainda não encontrou, busca em todas as ocorrências do aluno
        if not student_found:
            for tr in soup.find_all('tr'):
                tr_text = tr.get_text()
                if student_name in tr_text:
                    # Procura por células com números
                    cells = tr.find_all('td')
                    digits_cells = []
                    
                    for cell in cells:
                        cell_text = cell.get_text().strip()
                        if cell_text.isdigit():
                            digits_cells.append((cell, int(cell_text)))
                    
                    # Se encontrou pelo menos 3 células com dígitos consecutivos
                    if len(digits_cells) >= 3:
                        # Examina as últimas 3 células para ver se podem ser P, F, FJ
                        consecutive_found = False
                        for i in range(len(digits_cells) - 2):
                            # Verifica se as 3 células são consecutivas na linha
                            cell1_idx = cells.index(digits_cells[i][0])
                            cell2_idx = cells.index(digits_cells[i+1][0])
                            cell3_idx = cells.index(digits_cells[i+2][0])
                            
                            if cell2_idx == cell1_idx + 1 and cell3_idx == cell2_idx + 1:
                                # Provavelmente encontramos os totais P, F, FJ consecutivos
                                student_totals['P'] = digits_cells[i][1]
                                student_totals['F'] = digits_cells[i+1][1]
                                student_totals['FJ'] = digits_cells[i+2][1]
                                consecutive_found = True
                                logger.info(f"Totais consecutivos para {student_name}: P={student_totals['P']}, F={student_totals['F']}, FJ={student_totals['FJ']}")
                                break
                        
                        if consecutive_found:
                            student_found = True
                            break
                        
                        # Se não encontrou 3 células consecutivas, assume que são os últimos 3 valores
                        if not consecutive_found and not student_found:
                            last_three = digits_cells[-3:]
                            values = [value for _, value in last_three]
                            if len(values) == 3:
                                student_totals['P'] = values[0]
                                student_totals['F'] = values[1]
                                student_totals['FJ'] = values[2]
                                student_found = True
                                logger.info(f"Usando últimos 3 valores para {student_name}: P={student_totals['P']}, F={student_totals['F']}, FJ={student_totals['FJ']}")
                                break
        
        totals[student_name] = student_totals
    
    return totals

def analyze_f_marks(attendance_marks, months_found, education_type=None):
    """Analisa as marcações de falta ('F') por aluno e mês.
    
    Args:
        attendance_marks: Lista de marcações de presença/falta
        months_found: Conjunto de meses encontrados no documento
        education_type: Tipo de educação (infantil ou fundamental)
    """
    student_absences = defaultdict(lambda: defaultdict(int))
    
    # Filtra apenas as marcações 'F'
    f_marks = [mark for mark in attendance_marks if mark['mark'] == 'F' and mark['date'] is not None]
    
    for mark in f_marks:
        student = mark['student']
        month = mark['date']['month']
        student_absences[student][month] += 1
    
    # Converte para o formato final
    result = {}
    for student, absences in student_absences.items():
        # Cria um dicionário com todos os meses encontrados
        monthly_absences = {MONTH_NAMES.get(month, f"M{month}"): 0 for month in months_found}
        
        # Preenche os dados reais de faltas
        for month, count in absences.items():
            month_name = MONTH_NAMES.get(month, f"M{month}")
            monthly_absences[month_name] = count
        
        # Também armazena os dados numéricos para uso nas regras
        monthly_numeric = {}
        for month, count in absences.items():
            monthly_numeric[month] = count
        
        # Calcula a maior falta mensal para classificação
        maior_falta_mensal = max(absences.values()) if absences else 0
        
        # Cria a string formatada usando o nome abreviado dos meses
        formatted_absences = ', '.join([f"{month}:{count}" for month, count in monthly_absences.items()])
        
        result[student] = {
            'faltas_por_mes': monthly_numeric,  # Formato numérico para as regras
            'faltas_por_mes_formatado': monthly_absences,  # Formato com nomes para exibição
            'maior_falta_mensal': maior_falta_mensal,  # Para uso direto nas regras
            'faltas_por_mes_texto': formatted_absences
        }
    
    return result

def determine_education_type(class_name):
    """Determina o tipo de educação (obrigatória ou não)."""
    if not class_name:
        return "infantil"  # Default para não obrigatória
    
    class_name = class_name.upper()
    
    # Ensino obrigatório: fundamental e GT4/GT5
    if any(pattern in class_name for pattern in [
        '1º', '2º', '3º', '4º', '5º', '6º', '7º', '8º', '9º',
        '1 ANO', '2 ANO', '3 ANO', '4 ANO', '5 ANO', '6 ANO', '7 ANO', '8 ANO', '9 ANO',
        'GT4', 'GT 4', 'GT5', 'GT 5'
    ]):
        return "obrigatorio"  # Unificando todos como obrigatórios
    
    # Não obrigatório: educação infantil GT0-GT3
    if any(f"GT {i}" in class_name or f"GT{i}" in class_name for i in ["0", "1", "2", "3"]):
        return "nao_obrigatorio"
    
    # Se não conseguir identificar, assume infantil não obrigatório
    return "nao_obrigatorio"

def process_html_file(html_content):
    """Processa o arquivo HTML e extrai todas as informações relevantes."""
    logger.info("Iniciando processamento do arquivo HTML")
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1, 2, 3. Extrair informações básicas da escola usando a mesma função do analise_parser
        from .analise_parser import get_school_info
        school_info = get_school_info(html_content)
        
        # Extrai informações básicas
        basic_info = extract_basic_info(html_content)
        
        # Combina as informações das duas fontes (priorizando get_school_info)
        combined_info = {
            'school_name': school_info['unit_name'] if school_info['unit_name'] != 'Não identificada' else basic_info['school_name'],
            'class_name': school_info['class_name'] if school_info['class_name'] != 'Não identificada' else basic_info['class_name'],
            'school_days': school_info['school_days'] if school_info['school_days'] > 0 else basic_info['school_days']
        }
        
        # Determina o tipo de educação com base no nome da turma
        education_type = determine_education_type(combined_info['class_name'])
        logger.info(f"Tipo de educação: {education_type} para turma {combined_info['class_name']}")
        
        # Verifica se é GT3 - Ensino não obrigatório
        class_name_upper = combined_info['class_name'].upper()
        if 'GT3' in class_name_upper or 'GT 3' in class_name_upper or class_name_upper.startswith('GT3'):
            education_type = 'nao_obrigatorio'
            logger.info(f"Detectado GT3 como ensino não obrigatório: {class_name_upper}")
        
        # Garante que GT0, GT1, GT2, GT3 sejam sempre 'nao_obrigatorio'
        if any(f"GT{i}" in class_name_upper or f"GT {i}" in class_name_upper for i in ["0", "1", "2", "3"]):
            education_type = 'nao_obrigatorio'
            logger.info(f"Revalidado como ensino não obrigatório para GT0-GT3: {class_name_upper}")
        
        # 4. Extrair lista de alunos (usando a função do analise_parser se possível)
        try:
            from .analise_parser import get_student_list
            students = get_student_list(html_content)
            logger.info(f"Lista de alunos obtida de analise_parser: {len(students)} alunos")
        except Exception as e:
            logger.warning(f"Erro ao usar get_student_list de analise_parser: {str(e)}")
            # Fallback para o método atual
            students = extract_students(soup)
            logger.info(f"Lista de alunos obtida de direct_parser: {len(students)} alunos")
        
        # 5. Identificar as datas no documento
        dates, dates_by_month, months_found = extract_dates(soup)
        logger.info(f"Meses encontrados: {sorted(months_found)}")
        
        # Extrai as marcações de presença/falta
        attendance_marks = extract_attendance_values(soup)
        logger.info(f"Total de marcações extraídas: {len(attendance_marks)}")
        
        # 6-11. Analisa as faltas por mês para cada aluno
        student_absences = analyze_f_marks(attendance_marks, months_found, education_type)
        logger.info(f"Faltas por mês analisadas para {len(student_absences)} alunos")
        
        # Prepara o resultado final usando a mesma estrutura do analyze_elementary_file
        # Formatação do nome da turma: Garantir que turmas GT tenham o prefixo correto
        class_name = combined_info['class_name']
        # Se é um número seguido por uma letra (ex: "4 A"), converte para o formato "GT4 A"
        if re.match(r'^\d+\s*[A-Z]$', class_name):
            class_name = f"GT {class_name}"
        
        result = {
            'class_name': class_name,
            'education_type': education_type,
            'students': []
        }
        
        # 12-13. Para cada aluno, processa as informações
        for student in students:
            # Processa os totais para este aluno (usando a função de find_totals)
            student_totals = find_totals_in_html(html_content, student)
            
            # Cria o objeto de dados do aluno com informações básicas
            student_data = {
                'aluno': student,
                'P': student_totals['P'],
                'F': student_totals['F'],
                'FJ': student_totals['FJ'],
                'unidade': combined_info['school_name'],
                'escola': combined_info['school_name'],
                'turma': class_name,  # Usa o nome da turma formatado corretamente
                'dias_letivos': combined_info['school_days']
            }
            
            # Adiciona informações de faltas por mês
            if student in student_absences:
                student_data['faltas_por_mes'] = student_absences[student]['faltas_por_mes']
                student_data['faltas_por_mes_texto'] = student_absences[student]['faltas_por_mes_texto']
                student_data['maior_falta_mensal'] = student_absences[student]['maior_falta_mensal']
                logger.info(f"Aluno {student} - Maior falta mensal: {student_data['maior_falta_mensal']}")
            else:
                # Se não tem faltas registradas, cria um dicionário vazio com os meses encontrados
                faltas_por_mes = {month: 0 for month in months_found}  # Formato numérico para as regras
                student_data['faltas_por_mes'] = faltas_por_mes
                student_data['faltas_por_mes_texto'] = ', '.join([f"{MONTH_NAMES.get(month, f'M{month}')}:0" for month in months_found])
                student_data['maior_falta_mensal'] = 0
                logger.info(f"Aluno {student} - Sem faltas registradas")
            
            # Calcula percentual de presença
            total_dias = student_data['P'] + student_data['F'] + student_data['FJ']
            if total_dias > 0:
                student_data['percentual_presenca'] = round((student_data['P'] / total_dias) * 100, 1)
            else:
                student_data['percentual_presenca'] = 0
            
            result['students'].append(student_data)
        
        logger.info(f"Processamento concluído. {len(result['students'])} alunos processados.")
        return result
    
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        logger.exception("Detalhes do erro:")
        return {
            'class_name': None,
            'education_type': 'infantil',
            'students': []
        }

# Função wrapper para compatibilidade com a interface existente
def analyze_attendance_html(html_content):
    """Wrapper para process_html_file"""
    return process_html_file(html_content)