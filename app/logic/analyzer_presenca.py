import re
import logging
from bs4 import BeautifulSoup
from collections import defaultdict

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

def get_last_two_months_from_data(active_months_list):
    """
    Retorna os dois últimos meses cronológicos de uma lista de meses ativos.
    """
    if not active_months_list:
        return []
    
    # Garante inteiros e ordena (1 a 12)
    sorted_months = sorted([int(m) for m in active_months_list if isinstance(m, (int, str)) and str(m).isdigit()])
    
    # Retorna os dois últimos (ou todos se tiver menos de 2)
    return sorted_months[-2:] if len(sorted_months) >= 2 else sorted_months

# ==============================================================================
# LÓGICA DE NEGÓCIO
# ==============================================================================

def determine_education_type(class_name):
    if not class_name:
        return {"nivel": "infantil", "obrigatorio": False}
        
    class_name = class_name.upper().strip()
    result = {}
    
    # GT0-GT5
    gt_match = re.search(r'GT\s*0?([0-5])', class_name)
    if gt_match:
        gt_num = int(gt_match.group(1))
        result["nivel"] = "infantil"
        result["obrigatorio"] = gt_num >= 4 
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
    
    # --- DETERMINAÇÃO DOS MESES DE REFERÊNCIA ---
    # Usa a lista de 'active_months' coletada durante o parse (baseada em conteúdo de célula)
    # Se não existir (legado), tenta inferir pelas faltas (menos preciso)
    if 'active_months' in data_wrapper and data_wrapper['active_months']:
        last_months = get_last_two_months_from_data(data_wrapper['active_months'])
    else:
        # Fallback: coleta chaves de faltas de todos os alunos
        all_months_fallback = set()
        for s in students:
            all_months_fallback.update(s.get('faltas_por_mes', {}).keys())
        last_months = get_last_two_months_from_data(list(all_months_fallback))
    
    logger.info(f"Meses de referência para análise (Últimos 2 com dados): {last_months}")
    
    for student in students:
        status = []
        
        # Dados do aluno
        edu_type = student.get('education_type', 'infantil')
        is_compulsory = student.get('is_compulsory', False)
        
        # Totais
        try:
            total_p = int(student.get('P', 0))
            total_f = int(student.get('F', 0))
            total_fj = int(student.get('FJ', 0))
            
            total_oportunidades = total_p + total_f + total_fj  
            total_aulas_efetivas = total_p + total_f
            
            if total_aulas_efetivas > 0:
                perc_presenca_calc = (total_p / total_aulas_efetivas) * 100
            else:
                perc_presenca_calc = 100.0 

            if total_oportunidades > 0:
                perc_just_calc = (total_fj / total_oportunidades) * 100
            else:
                perc_just_calc = 0.0
                
        except:
            perc_presenca_calc = 100.0
            perc_just_calc = 0.0
            total_p = total_f = total_fj = 0

        # --- APLICAÇÃO DAS REGRAS ---
        
        is_faltoso = False
        is_monitorar_faltas = False
        
        # 1. REGRAS GERAIS (Percentual)
        if perc_presenca_calc < 60.0:
            is_faltoso = True
        elif 60.0 <= perc_presenca_calc < 70.0:
            is_monitorar_faltas = True
            
        # 2. REGRAS ESPECÍFICAS INFANTIL (Absolutas nos últimos meses)
        if edu_type == 'infantil' and not is_faltoso and not is_monitorar_faltas:
            
            monthly = student.get('faltas_por_mes', {})
            max_relevant_faults = 0
            
            # Verifica APENAS os meses identificados como 'last_months'
            if monthly and isinstance(monthly, dict):
                relevant_counts = []
                for mes, count in monthly.items():
                    if int(mes) in last_months:
                        relevant_counts.append(count)
                
                max_relevant_faults = max(relevant_counts) if relevant_counts else 0
            
            if is_compulsory: # GT4, GT5
                if max_relevant_faults >= 10:
                    is_faltoso = True
                elif max_relevant_faults >= 7:
                    is_monitorar_faltas = True
            
            else: # GT0-GT3
                if max_relevant_faults >= 12:
                    is_faltoso = True
                elif max_relevant_faults >= 10:
                    is_monitorar_faltas = True

        # Aplica Status
        if is_faltoso:
            status.append("Faltoso")
        elif is_monitorar_faltas:
            status.append("Monitorar Faltas")

        # 3. REGRAS DE FALTAS JUSTIFICADAS
        if perc_just_calc > 60.0:
            status.append("Muitas FJs")
        elif 45.0 <= perc_just_calc <= 60.0:
            status.append("Monitorar FJs")

        if not status:
            status.append("Regular")
            
        student['status'] = status
        student['classificacao'] = ", ".join(status)
        student['situacao'] = status 
        student['percentual_presenca'] = round(perc_presenca_calc, 1)
        student['percentual_justificado'] = round(perc_just_calc, 1)
        student['P'] = total_p
        student['F'] = total_f
        student['FJ'] = total_fj
        
        classified.append(student)
        
    return classified

# ==============================================================================
# PARSER HTML
# ==============================================================================

def get_school_info(html_content, filename=None):
    result = {'unit_name': 'Não identificada', 'class_name': 'Não identificada', 'school_days': 0}
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        prefixos_escola = ['CEI ', 'CENTRO ', 'CAIC ', 'EBM ', 'EM ', 'IR ', 'ER ', 'GE ', 'EB ']
        
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

        if filename:
            clean = filename.upper()
            gt_match = re.search(r'GT\s*(\d+)([A-Z]?)', clean)
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
        'LÍNGUA', 'ESTRANGEIRA', 'INGLÊS', 'EDUCAÇÃO', 'FÍSICA', 'ENSINO', 'RELIGIOSO',
        'VISTO', 'MINISTRANTE', 'RESPONSÁVEL', 'OBS'
    ]
    
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) > 5:
            for row in rows[1:]:
                cells = row.find_all('td')
                if not cells: continue
                for i in range(min(3, len(cells))):
                    text = cells[i].get_text().strip()
                    clean = re.sub(r'\d+', '', text).strip()
                    if len(clean) > 5 and len(clean.split()) >= 2 and not any(p in clean.upper() for p in palavras_excluidas) and ":" not in clean and "/" not in clean:
                        students.append(clean)
                        break

    if not students:
        for span in soup.find_all('span'):
            if not span.string: continue
            text = span.string.strip()
            style = span.get('style', '').lower()
            if ('bold' in style or text.isupper()) and len(text.split()) >= 2:
                clean = re.sub(r'\d+', '', text).strip()
                if len(clean) > 5 and not any(p in clean.upper() for p in palavras_excluidas) and ":" not in clean and "/" not in clean:
                    students.append(clean)
                    
    return list(dict.fromkeys(students))

def find_totals_in_html(soup, student_name):
    result = {'P': 0, 'F': 0, 'FJ': 0}
    
    pfj_tables = []
    all_tables = soup.find_all('table')
    for table in all_tables:
        rows = table.find_all('tr')
        for row_idx, row in enumerate(rows[:10]):
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text().strip().upper() for c in cells]
            
            if 'P' in texts and 'F' in texts and 'FJ' in texts:
                pfj_tables.append({
                    'table': table,
                    'header_row_idx': row_idx,
                    'p_idx': texts.index('P'),
                    'f_idx': texts.index('F'),
                    'fj_idx': texts.index('FJ')
                })
                break
    
    for table_info in pfj_tables:
        table = table_info['table']
        p_idx = table_info['p_idx']
        f_idx = table_info['f_idx']
        fj_idx = table_info['fj_idx']
        
        rows = table.find_all('tr')
        for row in rows[table_info['header_row_idx']+1:]:
            if student_name in row.get_text():
                cells = row.find_all('td')
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
                    
                    if result['P'] > 0 or result['F'] > 0 or result['FJ'] > 0:
                        return result
                except: pass

    student_elements = soup.find_all(string=lambda t: t and student_name in str(t))
    for elem in student_elements:
        row = elem.find_parent('tr')
        if not row: continue
        
        numbers = []
        for cell in row.find_all('td'):
            txt = cell.get_text().strip()
            if txt.isdigit() and len(txt) < 4:
                numbers.append(int(txt))
        
        if len(numbers) >= 3:
            result['P'] = numbers[-3]
            result['F'] = numbers[-2]
            result['FJ'] = numbers[-1]
            return result

    return result

def process_student_attendance(soup, student_name):
    """
    Conta faltas e identifica meses ativos (com dados).
    """
    faltas_por_mes = defaultdict(int)
    active_months = set() # Novo: Coleta meses que tiveram ALGUM dado
    
    student_elements = soup.find_all(string=lambda t: t and student_name in str(t))
    
    for elem in student_elements:
        current_row = elem.find_parent('tr')
        if not current_row: continue
        
        parent_table = current_row.find_parent('table')
        if not parent_table: continue
        
        date_map = {} 
        rows = parent_table.find_all('tr')
        
        try:
            student_row_idx = rows.index(current_row)
        except ValueError:
            continue
            
        for i in range(student_row_idx - 1, -1, -1):
            row = rows[i]
            cells = row.find_all(['td', 'th'])
            found_date = False
            
            for idx, cell in enumerate(cells):
                txt = cell.get_text().strip()
                match = re.search(r'(\d{1,2})/(\d{1,2})', txt)
                if match:
                    try:
                        month = int(match.group(2))
                        if 1 <= month <= 12:
                            date_map[idx] = month
                            found_date = True
                    except: pass
            
            if found_date:
                break
        
        if date_map:
            cells = current_row.find_all('td')
            for idx, cell in enumerate(cells):
                if idx in date_map:
                    content = cell.get_text().strip().upper()
                    
                    # REGRA CRÍTICA: Se a célula tem conteúdo (F, P, ., etc), o mês existiu
                    # Ignora células vazias (futuro)
                    if content: 
                        active_months.add(date_map[idx])
                    
                    if content == 'F':
                        faltas_por_mes[date_map[idx]] += 1

    txt = " ".join([f"{get_month_name(m)}:{c}" for m, c in sorted(faltas_por_mes.items()) if c > 0])
    return {
        'faltas_por_mes': dict(faltas_por_mes), 
        'faltas_por_mes_texto': txt,
        'active_months': active_months
    }

def analyze_attendance_html(html_content, filename=None):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        info = get_school_info(html_content, filename)
        students = get_student_list(soup)
        edu_info = determine_education_type(info['class_name'])
        
        student_data_list = []
        global_active_months = set() # Acumula meses ativos de toda a turma
        
        for name in students:
            totals = find_totals_in_html(soup, name)
            attendance = process_student_attendance(soup, name)
            
            # Acumula meses que tiveram dados
            global_active_months.update(attendance['active_months'])
            
            # Ajuste de totais para Infantil
            total_calc = totals['P'] + totals['F'] + totals['FJ']
            if total_calc == 0 and edu_info['nivel'] == 'infantil' and attendance['faltas_por_mes']:
                manual_f = sum(attendance['faltas_por_mes'].values())
                if manual_f > 0:
                    totals['F'] = manual_f
            
            student_data_list.append({
                'aluno': name, 'name': name,
                'turma': info['class_name'], 'escola': info['unit_name'],
                'P': totals['P'], 'F': totals['F'], 'FJ': totals['FJ'],
                'faltas_por_mes': attendance['faltas_por_mes'],
                'faltas_por_mes_texto': attendance['faltas_por_mes_texto'],
                'education_type': edu_info['nivel'],
                'is_compulsory': edu_info['obrigatorio']
            })
            
        return {
            'school_data': info,
            'student_data': student_data_list,
            'active_months': list(global_active_months) # Passa para a classificação
        }
    except Exception as e:
        logger.error(f"Erro analyzer: {e}")
        return None