import re
import logging
import unicodedata
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime

# Configuração de Logger
logger = logging.getLogger(__name__)

# ==============================================================================
# UTILS
# ==============================================================================

MONTH_NAMES = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

def get_month_name(month_number):
    try:
        return MONTH_NAMES.get(int(month_number), str(month_number))
    except:
        return str(month_number)

# ==============================================================================
# LÓGICA DE NEGÓCIO
# ==============================================================================

def determine_education_type(class_name):
    if not class_name:
        return {"nivel": "infantil", "obrigatorio": False}
        
    class_name = class_name.upper().strip()
    result = {}
    
    # GT0-GT5
    gt_match = re.search(r'GT\s*([0-5])', class_name)
    if gt_match:
        gt_num = int(gt_match.group(1))
        result["nivel"] = "infantil"
        result["obrigatorio"] = gt_num >= 4 # GT4 e GT5 são obrigatórias
        return result
    
    # Fundamental
    ano_match = re.search(r'([1-9])(º|°|\s)?(\s)*(ANO|SERIE|SÉRIE)', class_name)
    if ano_match:
        result["nivel"] = "fundamental"
        result["obrigatorio"] = True
        return result
    
    result["nivel"] = "infantil"
    result["obrigatorio"] = False
    return result

def apply_classification_rules(data_wrapper):
    if not data_wrapper or 'student_data' not in data_wrapper:
        return []
        
    students = data_wrapper['student_data']
    classified = []
    
    for student in students:
        status = []
        is_compulsory = student.get('is_compulsory', False)
        
        limit_faltoso = 10 if is_compulsory else 12
        limit_monitor = 7 if is_compulsory else 10
        
        monthly = student.get('faltas_por_mes', {})
        max_monthly = 0
        if monthly and isinstance(monthly, dict):
            valores = [v for v in monthly.values() if isinstance(v, (int, float))]
            max_monthly = max(valores) if valores else 0
            
        try:
            perc_presenca = float(student.get('percentual_presenca', 0))
        except: perc_presenca = 0
            
        try:
            perc_just = float(student.get('percentual_justificado', 0))
        except: perc_just = 0
        
        if max_monthly >= limit_faltoso or (perc_presenca < 60 and perc_presenca > 0):
            status.append("Faltoso")
        elif max_monthly >= limit_monitor or (perc_presenca < 75 and perc_presenca > 0):
            status.append("Monitorar Faltas")
            
        if perc_just >= 60:
            status.append("Muitas FJs")
        elif perc_just >= 45:
            status.append("Monitorar FJs")
            
        if not status:
            status.append("Regular")
            
        student['status'] = status
        student['classificacao'] = ", ".join(status)
        student['situacao'] = status 
        
        classified.append(student)
        
    return classified

# ==============================================================================
# PARSER HTML (LÓGICA RESTAURADA E CORRIGIDA)
# ==============================================================================

def get_school_info(html_content, filename=None):
    result = {'unit_name': 'Não identificada', 'class_name': 'Não identificada', 'school_days': 0}
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        prefixos_escola = ['CEI ', 'CENTRO ', 'CAIC ', 'EBM ', 'EM ', 'IR ', 'ER ', 'GE ', 'EB ']
        
        # 1. Escola
        escola_encontrada = False
        for table in soup.find_all('table')[:5]:
            if escola_encontrada: break
            for span in table.find_all('span'):
                if not span.get_text(): continue
                texto = span.get_text().strip().upper()
                for prefixo in prefixos_escola:
                    if texto.startswith(prefixo):
                        if not any(p in texto for p in ['REGISTRO', 'RELATÓRIO', 'TURMA']):
                            result['unit_name'] = texto
                            escola_encontrada = True
                            break
                if escola_encontrada: break
        
        if not escola_encontrada and filename:
            result['unit_name'] = filename.split('_')[0].upper().replace('.HTML', '')

        # 2. Turma
        if filename:
            clean = filename.upper()
            gt_match = re.search(r'GT(\d+)([A-Z]?)', clean)
            ano_match = re.search(r'(\d+)ANO(\d*)', clean)
            if gt_match:
                result['class_name'] = f"GT{gt_match.group(1)}{gt_match.group(2) or ''}"
            elif ano_match:
                turma = ano_match.group(2) or ''
                result['class_name'] = f"{ano_match.group(1)}º ANO{' - ' + turma if turma else ''}"
        
        if result['class_name'] == 'Não identificada':
            all_text = soup.get_text()
            turma_match = re.search(r'TURMA:\s*(GT\s*\d+\s*[A-Z]?|(\d+)[ºª°]?\s*ANO\s*[-–—]?\s*(\d+)?)', all_text, re.IGNORECASE)
            if turma_match:
                if 'GT' in turma_match.group(0).upper():
                    result['class_name'] = turma_match.group(1).strip().replace(' ', '').upper()
                else:
                    ano = turma_match.group(2)
                    turma = turma_match.group(3) if len(turma_match.groups()) > 2 else ''
                    result['class_name'] = f"{ano}º ANO - {turma}" if turma else f"{ano}º ANO"

        # 3. Dias Letivos
        days_match = re.search(r'DIAS\s+LETIVOS\s*[:=]?\s*(\d+)', soup.get_text().upper())
        if days_match:
            result['school_days'] = int(days_match.group(1))
            
    except Exception as e:
        logger.error(f"Erro info: {e}")
    return result

def get_student_list(soup):
    students = []
    palavras_excluidas = [
        'PROFESSOR', 'ALUNO', 'TOTAL', 'PALHOÇA', 'CEI', 'CONVIVER', 'DIAS', 'LETIVOS',
        'MATEMÁTICA', 'PORTUGUESA', 'GEOGRAFIA', 'HISTÓRIA', 'CIÊNCIAS', 'ARTE', 'DATA',
        'COMPONENTE', 'CURRICULAR', 'MUNICÍPIO', 'RELATÓRIO', 'BIMESTRE', 'SEMESTRE',
        'LÍNGUA', 'ESTRANGEIRA', 'INGLÊS', 'EDUCAÇÃO', 'FÍSICA', 'ENSINO', 'RELIGIOSO'
    ]
    
    # Método 1: Células de tabela (mais comum em listas de chamada)
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) > 5:
            for row in rows[1:]:
                cells = row.find_all('td')
                if not cells: continue
                for i in range(min(3, len(cells))):
                    text = cells[i].get_text().strip()
                    clean = re.sub(r'\d+', '', text).strip()
                    if len(clean) > 5 and len(clean.split()) >= 2 and not any(p in clean.upper() for p in palavras_excluidas) and ":" not in clean:
                        students.append(clean)
                        break

    # Método 2: Spans em negrito (fallback)
    if not students:
        for span in soup.find_all('span'):
            if not span.string: continue
            text = span.string.strip()
            style = span.get('style', '').lower()
            if ('bold' in style or text.isupper()) and len(text.split()) >= 2:
                clean = re.sub(r'\d+', '', text).strip()
                if len(clean) > 5 and not any(p in clean.upper() for p in palavras_excluidas) and ":" not in clean:
                    students.append(clean)
                    
    return list(dict.fromkeys(students))

def find_totals_in_html(soup, student_name):
    """
    Busca os totais de P, F e FJ para um aluno específico.
    LÓGICA RESTAURADA (CÓDIGO ANTIGO):
    1. Encontra TODAS as tabelas de totais (pode haver várias).
    2. Procura o aluno dentro dessas tabelas.
    3. Fallback: Procura 3 números no final de qualquer linha do aluno.
    """
    result = {'P': 0, 'F': 0, 'FJ': 0}
    
    # PASSO 1: Encontrar todas as tabelas de totais que contém P, F, FJ
    p_headers = soup.find_all('span', string='P')
    pfj_tables = []
    
    for p_header in p_headers:
        parent_td = p_header.find_parent('td')
        if not parent_td: continue
        
        # Verifica se o próximo elemento é o cabeçalho F
        next_td = parent_td.find_next_sibling('td')
        if next_td and next_td.find('span', string='F'):
            # E o próximo é o cabeçalho FJ
            next_next_td = next_td.find_next_sibling('td')
            if next_next_td and next_next_td.find('span', string='FJ'):
                # Encontramos uma tabela com os cabeçalhos P, F, FJ em sequência
                header_table = parent_td.find_parent('table')
                header_row = parent_td.find_parent('tr')
                if header_table and header_row:
                    try:
                        row_cells = list(header_row.find_all('td'))
                        pfj_tables.append({
                            'table': header_table,
                            'header_row': header_row,
                            'p_idx': row_cells.index(parent_td),
                            'f_idx': row_cells.index(next_td),
                            'fj_idx': row_cells.index(next_next_td)
                        })
                    except: pass

    # Se não achou tabelas por spans, tenta buscar tabelas onde o texto está direto no TD
    if not pfj_tables:
         tables = soup.find_all('table')
         # Olha as últimas tabelas (onde geralmente estão os totais)
         for table in tables[-3:]:
             rows = table.find_all('tr')
             for row in rows[:5]: 
                 cells = row.find_all('td')
                 texts = [c.get_text().strip().upper() for c in cells]
                 if 'P' in texts and 'F' in texts and 'FJ' in texts:
                     pfj_tables.append({
                         'table': table,
                         'header_row': row,
                         'p_idx': texts.index('P'),
                         'f_idx': texts.index('F'),
                         'fj_idx': texts.index('FJ')
                     })
                     break

    logger.info(f"Encontradas {len(pfj_tables)} tabelas de totais")

    # PASSO 2: Para cada tabela de totais, procurar o aluno e extrair os valores
    for table_info in pfj_tables:
        table = table_info['table']
        header_row = table_info['header_row']
        p_idx = table_info['p_idx']
        f_idx = table_info['f_idx']
        fj_idx = table_info['fj_idx']
        
        # Itera sobre todas as linhas da tabela (exceto cabeçalho)
        for tr in table.find_all('tr'):
            if tr == header_row: continue
            
            if student_name in tr.get_text():
                cells = tr.find_all('td')
                try:
                    if p_idx < len(cells):
                        val = cells[p_idx].get_text().strip()
                        if val.isdigit(): result['P'] = int(val)
                    if f_idx < len(cells):
                        val = cells[f_idx].get_text().strip()
                        if val.isdigit(): result['F'] = int(val)
                    if fj_idx < len(cells):
                        val = cells[fj_idx].get_text().strip()
                        if val.isdigit(): result['FJ'] = int(val)
                        
                    # Se encontrou valores, retorna
                    if result['P'] > 0 or result['F'] > 0 or result['FJ'] > 0:
                        logger.info(f"Totais encontrados para {student_name} na tabela")
                        return result
                except: pass

    # PASSO 3: Fallback (Números soltos no final da linha)
    # Procura TODAS as ocorrências do aluno no HTML (spans)
    student_spans = []
    for span in soup.find_all('span'):
        if span.string and student_name in span.string:
            student_spans.append(span)
            
    for span in student_spans:
        td = span.find_parent('td')
        if not td: continue
        tr = td.find_parent('tr')
        if not tr: continue
        
        # Extrai números desta linha
        numbers = []
        for cell in tr.find_all('td'):
            txt = cell.get_text().strip()
            if txt.isdigit() and len(txt) < 5:
                numbers.append(int(txt))
        
        # Se tem pelo menos 3 números, pega os últimos 3 como P, F, FJ
        if len(numbers) >= 3:
            result['P'] = numbers[-3]
            result['F'] = numbers[-2]
            result['FJ'] = numbers[-1]
            logger.info(f"Fallback totais para {student_name}: {result}")
            return result
            
    return result

def process_student_attendance(soup, student_name):
    """Conta faltas por mês."""
    faltas_por_mes = defaultdict(int)
    date_cols = {}
    
    # 1. Mapeia colunas de data (DD/MM)
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            for idx, cell in enumerate(row.find_all(['td', 'th'])):
                txt = cell.get_text().strip()
                match = re.search(r'(\d{1,2})/(\d{1,2})', txt)
                if match:
                    try:
                        month = int(match.group(2))
                        if 1 <= month <= 12: date_cols[idx] = month
                    except: pass

    # 2. Conta faltas
    student_cells = soup.find_all(string=lambda t: t and student_name in str(t))
    for s_cell in student_cells:
        row = s_cell.find_parent('tr')
        if not row: continue
        cells = row.find_all('td')
        for idx, cell in enumerate(cells):
            if idx in date_cols and cell.get_text().strip().upper() == 'F':
                faltas_por_mes[date_cols[idx]] += 1

    txt = " ".join([f"{get_month_name(m)}:{c}" for m, c in sorted(faltas_por_mes.items()) if c > 0])
    return {'faltas_por_mes': dict(faltas_por_mes), 'faltas_por_mes_texto': txt}

def analyze_attendance_html(html_content, filename=None):
    """
    Função principal chamada pelo routes.py.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        info = get_school_info(html_content, filename)
        students = get_student_list(soup)
        edu_info = determine_education_type(info['class_name'])
        
        student_data_list = []
        for name in students:
            # 1. Extrai totais (P, F, FJ) - Lógica restaurada
            totals = find_totals_in_html(soup, name)
            
            # 2. Extrai faltas por mês
            attendance = process_student_attendance(soup, name)
            
            # 3. REGRA CRÍTICA: Fundamental = Faltas Mensais N/A
            if edu_info['nivel'] == 'fundamental':
                attendance['faltas_por_mes'] = {}
                attendance['faltas_por_mes_texto'] = "N/A"
            
            # 4. Cálculo de percentuais e fallback para totais zerados (Infantil apenas)
            total_calc = totals['P'] + totals['F'] + totals['FJ']
            
            # Se totais zerados no Infantil, tenta usar a contagem mensal como "F"
            if total_calc == 0 and edu_info['nivel'] == 'infantil' and attendance['faltas_por_mes']:
                manual_f = sum(attendance['faltas_por_mes'].values())
                if manual_f > 0:
                    totals['F'] = manual_f
                    total_calc = manual_f # Assume que são todas faltas se não temos P ou FJ
            
            perc_p = 0
            if total_calc > 0:
                perc_p = round((totals['P'] / total_calc * 100), 1)
            
            total_faltas = totals['F'] + totals['FJ']
            perc_j = 0
            if total_faltas > 0:
                perc_j = round((totals['FJ'] / total_faltas * 100), 1)
            
            student_data_list.append({
                'aluno': name, 'name': name,
                'turma': info['class_name'], 'escola': info['unit_name'],
                'P': totals['P'], 'F': totals['F'], 'FJ': totals['FJ'],
                'percentual_presenca': perc_p,
                'percentual_justificado': perc_j,
                'faltas_por_mes': attendance['faltas_por_mes'],
                'faltas_por_mes_texto': attendance['faltas_por_mes_texto'],
                'education_type': edu_info['nivel'],
                'is_compulsory': edu_info['obrigatorio']
            })
            
        return {
            'school_data': info,
            'student_data': student_data_list
        }
    except Exception as e:
        logger.error(f"Erro analyzer: {e}")
        return None