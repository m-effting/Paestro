import re
import io
import logging
import datetime
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from copy import copy

# Configuração de Logger
logger = logging.getLogger(__name__)

# ==============================================================================
# FUNÇÕES AUXILIARES DE EXTRAÇÃO
# ==============================================================================

def extract_date_from_filename(filename):
    """Extrai data do nome do arquivo no formato DD/MM/YYYY"""
    match = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}"
    return None

def extract_date_from_content(df):
    """Busca data nas primeiras linhas do arquivo Excel"""
    for _, row in df.iloc[:5].iterrows():
        row_str = ' '.join([str(val) for val in row.values if pd.notna(val)])
        match = re.search(r'(\d{2}/\d{2}/\d{4})', row_str)
        if match:
            return match.group(1)
    return None

def extract_school_info_from_header(df):
    """Extrai nome da unidade e período do cabeçalho do arquivo Excel"""
    school_name = None
    period = None
    
    for _, row in df.iloc[:10].iterrows():
        row_str = ' '.join([str(val) for val in row.values if pd.notna(val)]).upper()
        
        if not school_name:
            school_patterns = [
                r'UNIDADE[:\s]+([A-ZÁÊÇÕ\s]+?)(?:\s+PERÍODO|\s+TURNO|\s+MATUTINO|\s+VESPERTINO|\s+INTEGRAL|$)',
                r'CEI[:\s]+([A-ZÁÊÇÕ\s]+?)(?:\s+PERÍODO|\s+TURNO|\s+MATUTINO|\s+VESPERTINO|\s+INTEGRAL|$)',
                r'([A-ZÁÊÇÕ\s]+CEI[A-ZÁÊÇÕ\s]*?)(?:\s+PERÍODO|\s+TURNO|\s+MATUTINO|\s+VESPERTINO|\s+INTEGRAL|$)',
                r'CEI\s+([A-ZÁÊÇÕ\s]+?)\s+(?:MATUTINO|VESPERTINO|INTEGRAL)'
            ]
            for pattern in school_patterns:
                match = re.search(pattern, row_str)
                if match:
                    school_name = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
                    break
        
        if not period:
            if 'MATUTINO' in row_str: period = 'MATUTINO'
            elif 'VESPERTINO' in row_str: period = 'VESPERTINO'
            elif 'INTEGRAL' in row_str: period = 'INTEGRAL'
            elif 'NOTURNO' in row_str: period = 'NOTURNO'
    
    return school_name, period

def extract_annotations_from_file(df, filename):
    """Extrai anotações dos arquivos de chamada."""
    anotacoes = []
    try:
        data_arquivo = None
        date_match = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', filename)
        if date_match:
            day, month, _ = date_match.groups()
            data_arquivo = f"{day.zfill(2)}-{month.zfill(2)}"
        
        for i in range(min(20, len(df))):
            for col_idx, col in enumerate(df.columns):
                try:
                    cell_value = str(df.iloc[i, col_idx])
                    if pd.notna(cell_value) and "ANOTAÇÕES" in cell_value.upper():
                        for next_row in range(i + 1, min(i + 10, len(df))):
                            try:
                                next_cell_value = str(df.iloc[next_row, col_idx])
                                if pd.isna(next_cell_value) or next_cell_value.strip() == "" or next_cell_value == "nan":
                                    break
                                anotacao_texto = next_cell_value.strip()
                                anotacao_formatada = f"({data_arquivo}): {anotacao_texto}" if data_arquivo else anotacao_texto
                                if anotacao_formatada not in anotacoes:
                                    anotacoes.append(anotacao_formatada)
                            except: break
                        return anotacoes
                except: continue
    except Exception as e:
        logger.error(f"Erro ao extrair anotações: {e}")
    return anotacoes

def detect_observacoes(row, aluno_col_idx):
    """Detecta observações em uma linha."""
    for idx, val in enumerate(row):
        if pd.isna(val) or idx <= aluno_col_idx: continue
        val_str = str(val).strip()
        if len(val_str) > 5 and val_str.upper() not in ['P', 'F', 'FJ'] and not re.match(r'^\d+[.,]?\d*$', val_str):
            return val_str
    return ""

def normalize_turma_name(turma):
    """Normaliza o nome da turma."""
    if not turma or not isinstance(turma, str): return "Turma Não Identificada"
    turma = turma.strip()
    
    # Filtros de segurança
    invalid_patterns = [r'\d{1,2}/\d{1,2}/\d{2,4}', r'MUNICH', r'GUILHERME', r'DATA E HORA', r'PROFESSOR']
    for pattern in invalid_patterns:
        if re.search(pattern, turma.upper()): return "Turma Não Identificada"
    
    turma = turma.lower().replace('º', 'o').replace('°', 'o').replace('ª', 'a')
    turma = re.sub(r'\b(serie|série)\b', 'ano', turma)
    turma = re.sub(r'\s*[-_:]\s*', ' - ', turma)
    turma = re.sub(r'g\.?t\.?\s*(\d+)', r'gt\1', turma)
    
    ano_match = re.search(r'(\d+)o?\s*ano\s*[-\s]\s*(\d+|[a-z])', turma)
    gt_match = re.search(r'gt\s*(\d+)\s*[-\s]?\s*([a-z])?', turma)
    
    if ano_match:
        numero, sufixo = ano_match.groups()
        return f"{numero}º ANO - {sufixo.upper()}"
    elif gt_match:
        numero = gt_match.group(1)
        sufixo = gt_match.group(2).upper() if gt_match.group(2) else ""
        return f"GT{numero} - {sufixo}" if sufixo else f"GT{numero}"
    
    if re.search(r'\b(ano|série|serie|turma|gt)\b', turma, re.IGNORECASE):
        return ' '.join(p.capitalize() for p in turma.split())
        
    return "Turma Não Identificada"

def is_valid_student_name(name):
    """Verifica se é um nome de aluno válido."""
    if not name or not isinstance(name, str) or not name.strip(): return False
    name = name.strip()
    
    invalid_patterns = [r'^TURMA', r'^TOTAL', r'^PROFESSOR', r'^DATA', r'RELATÓRIO', r'MATUTINO', 
                        r'VESPERTINO', r'\d{1,2}/\d{1,2}', r'MUNICH', r'GUILHERME']
    
    if any(re.search(p, name.upper()) for p in invalid_patterns): return False
    if re.match(r'^\d+$', name): return False
    
    # Regra: Pelo menos duas palavras, sem caracteres estranhos
    if ' ' in name and not re.search(r'[*+=&%$#@!?><\[\]\{\}\\|0-9]', name):
        words = name.split()
        if len(words) >= 2 and all(len(w) >= 2 for w in words):
            return True
            
    return False

def is_analysis_file(filename, content=None):
    """Verifica se é arquivo de análise."""
    if filename.startswith("GE_") or "PEQUENO_PRINCIPE" in filename.upper(): return False
    
    # Se tem data e período no nome, é chamada
    if re.search(r'\d{2}-\d{2}-\d{4}', filename) and ('MATUTINO' in filename.upper() or 'VESPERTINO' in filename.upper()):
        return False
        
    indicators = ["analise", "análise", "analitico", "consolidado", "resumo"]
    if any(i in filename.lower() for i in indicators): return True
    
    if content:
        try:
            with io.BytesIO(content) as buffer:
                df = pd.read_excel(buffer, nrows=20)
                cols = ' '.join(str(c).lower() for c in df.columns)
                if any(i in cols for i in ["percentual", "total faltas", "estatística"]): return True
        except: pass
        
    return False

def process_file(file_content, filename):
    """Processa arquivo Excel para extração de dados."""
    is_call = not is_analysis_file(filename, file_content)
    
    result = {
        'filename': filename, 'is_analysis': not is_call,
        'date': None, 'turmas': [], 'alunos_data': {}, 'df': None
    }
    
    try:
        with io.BytesIO(file_content) as buffer:
            df = pd.read_excel(buffer)
            if not is_call:
                result['df'] = df
                return result
            
            # Lógica para arquivos de chamada
            date_match = re.search(r'(\d{2}-\d{2}-\d{4})', filename)
            if date_match:
                result['date'] = date_match.group(1).replace('-', '/')
            
            if not result['date']: result['date'] = extract_date_from_content(df)
            
            # Processamento de alunos e turmas
            turma_atual = None
            turmas_encontradas = []
            
            for _, row in df.iterrows():
                row_str = ' '.join([str(val) for val in row.values if pd.notna(val)])
                
                # Detecção de turma na linha
                turma_match = re.search(r'(GT\s*\d+|G\.T\.\s*\d+|\d+º?\s*ANO)', row_str, re.IGNORECASE)
                if turma_match and 'TURMA' in row_str.upper():
                    turma_atual = normalize_turma_name(turma_match.group(0))
                    if turma_atual not in turmas_encontradas: turmas_encontradas.append(turma_atual)
                
                # Detecção de aluno
                for col_idx, val in enumerate(row):
                    if pd.isna(val): continue
                    val_str = str(val).strip()
                    
                    if is_valid_student_name(val_str):
                        turma_key = turma_atual if turma_atual else "Turma Não Identificada"
                        if turma_key not in result['turmas']: result['turmas'].append(turma_key)
                        
                        # Status
                        status = "P"
                        if col_idx+1 < len(row):
                            stat_val = str(row[col_idx+1]).strip().upper()
                            if stat_val in ["F", "FJ", "FALTA"]: status = "F" if stat_val != "FJ" else "FJ"
                        
                        obs = detect_observacoes(row, col_idx)
                        
                        key = f"{turma_key}|{val_str}"
                        result['alunos_data'][key] = {
                            'turma': turma_key, 'nome': val_str,
                            'status': status, 'observacao': obs
                        }
            
            result['anotacoes'] = extract_annotations_from_file(df, filename)
            return result
            
    except Exception as e:
        logger.error(f"Erro processando {filename}: {e}")
        return result

# ==============================================================================
# FUNÇÃO PRINCIPAL
# ==============================================================================

def generate_consolidated_report(chamada_files, analise_files):
    """
    Função principal chamada pelo routes.py.
    Recebe listas de arquivos (FileStorage ou dict) e gera o Excel final.
    """
    files_data = []
    
    # Normaliza a entrada para o formato esperado
    all_files = (chamada_files or []) + (analise_files or [])
    
    for f in all_files:
        # Se for FileStorage (upload do Flask)
        if hasattr(f, 'read'):
            f.seek(0)
            content = f.read()
            filename = f.filename
        else:
            # Se já for dicionário
            content = f.get('content')
            filename = f.get('filename')
            
        files_data.append({'filename': filename, 'content': content})

    # Lógica central de geração
    try:
        report_data = generate_improved_report_logic(files_data)
        
        # Se retornou dicionário, pega o binário
        if isinstance(report_data, dict):
            return io.BytesIO(report_data['excel_data'])
        return io.BytesIO(report_data)
        
    except Exception as e:
        logger.error(f"Erro fatal na geração do relatório: {e}")
        # Retorna um Excel de erro
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(1, 1, f"Erro: {str(e)}")
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return out

def generate_improved_report_logic(files_data):
    """Lógica interna de geração (antigo generate_improved_report)"""
    regular_files = [f for f in files_data if not is_analysis_file(f['filename'], f['content'])]
    analysis_files = [f for f in files_data if is_analysis_file(f['filename'], f['content'])]
    
    all_data = []
    all_dates = set()
    all_turmas = set()
    
    # 1. Processa arquivos de Chamada
    for f in regular_files:
        data = process_file(f['content'], f['filename'])
        if data['date']: all_dates.add(data['date'])
        
        # Normaliza turmas
        normalized_alunos = {}
        for key, info in data['alunos_data'].items():
            turma_norm = normalize_turma_name(info['turma'])
            all_turmas.add(turma_norm)
            info['turma'] = turma_norm
            normalized_alunos[f"{turma_norm}|{info['nome']}"] = info
            
        data['alunos_data'] = normalized_alunos
        all_data.append(data)
        
    # Ordenação
    sorted_dates = sorted(list(all_dates), key=lambda d: datetime.datetime.strptime(d, '%d/%m/%Y') if d else datetime.datetime.max)
    sorted_turmas = sorted(list(all_turmas))
    
    # 2. Criação do Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CHAMADAS"
    
    # Cabeçalhos
    ws.cell(1, 1, "RELATÓRIO CONSOLIDADO").font = Font(bold=True, size=14, color="FFFFFF")
    ws.cell(1, 1).fill = PatternFill("solid", fgColor="1F4E78")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(sorted_dates)+3)
    
    # Linha de colunas
    headers = ["ALUNO"] + sorted_dates + ["OBSERVAÇÕES"]
    for idx, h in enumerate(headers, 1):
        cell = ws.cell(4, idx, h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4472C4")
        ws.column_dimensions[get_column_letter(idx)].width = 15 if idx > 1 else 40
        if h == "OBSERVAÇÕES": ws.column_dimensions[get_column_letter(idx)].width = 60

    # 3. Preenchimento de Dados
    current_row = 5
    for turma in sorted_turmas:
        # Cabeçalho da Turma
        ws.cell(current_row, 1, f"TURMA: {turma}").font = Font(bold=True)
        current_row += 1
        
        # Coleta alunos desta turma de todos os arquivos
        alunos_turma = set()
        for d in all_data:
            for k, v in d['alunos_data'].items():
                if v['turma'] == turma: alunos_turma.add(v['nome'])
        
        for aluno in sorted(alunos_turma):
            ws.cell(current_row, 1, aluno)
            
            obs_list = []
            for date_idx, date in enumerate(sorted_dates):
                status = "-"
                # Busca status neste dia
                for d in all_data:
                    if d['date'] == date:
                        key = f"{turma}|{aluno}"
                        if key in d['alunos_data']:
                            st = d['alunos_data'][key]['status']
                            status = st
                            
                            # Cores
                            color = "FFFFFF"
                            if st == "F": color = "FFCCCC"
                            elif st == "FJ": color = "FFFFCC"
                            elif st == "P": color = "CCFFCC"
                            
                            cell = ws.cell(current_row, date_idx+2, st)
                            cell.fill = PatternFill("solid", fgColor=color)
                            cell.alignment = Alignment(horizontal='center')
                            
                            # Coleta obs
                            obs = d['alunos_data'][key].get('observacao')
                            if obs: obs_list.append(f"({date}): {obs}")
            
            # Coluna observações
            if obs_list:
                ws.cell(current_row, len(sorted_dates)+2, "\n".join(obs_list)).alignment = Alignment(wrap_text=True)
                
            current_row += 1
        current_row += 1

    # 4. Aba de Monitoramento
    ws_mon = wb.create_sheet("MONITORAR")
    headers_mon = ["ALUNO", "TURMA", "FALTAS", "PRIORIDADE", "OBSERVAÇÃO"]
    for idx, h in enumerate(headers_mon, 1):
        ws_mon.cell(1, idx, h).font = Font(bold=True, color="FFFFFF")
        ws_mon.cell(1, idx).fill = PatternFill("solid", fgColor="4472C4")
        ws_mon.column_dimensions[get_column_letter(idx)].width = 20
    ws_mon.column_dimensions['E'].width = 60

    # Lógica simplificada de monitoramento (pode ser expandida conforme regras do arquivo original)
    mon_row = 2
    for turma in sorted_turmas:
        alunos_turma = set()
        for d in all_data:
            for k, v in d['alunos_data'].items():
                if v['turma'] == turma: alunos_turma.add(v['nome'])
        
        for aluno in sorted(alunos_turma):
            faltas = 0
            total_dias = 0
            datas_falta = []
            
            for d in all_data:
                key = f"{turma}|{aluno}"
                if key in d['alunos_data']:
                    total_dias += 1
                    if d['alunos_data'][key]['status'] in ['F', 'FJ']:
                        faltas += 1
                        datas_falta.append(d['date'])
            
            if faltas > 0:
                prioridade = "ALTA" if (total_dias > 0 and faltas == total_dias) else "MÉDIA"
                ws_mon.cell(mon_row, 1, aluno)
                ws_mon.cell(mon_row, 2, turma)
                ws_mon.cell(mon_row, 3, f"{faltas}/{total_dias}")
                ws_mon.cell(mon_row, 4, prioridade)
                ws_mon.cell(mon_row, 5, f"Faltas em: {', '.join(filter(None, datas_falta))}")
                mon_row += 1

    # 5. Abas de Análise (Cópia fiel)
    if analysis_files:
        for af in analysis_files:
            try:
                wb_analysis = openpyxl.load_workbook(io.BytesIO(af['content']))
                for sheet_name in wb_analysis.sheetnames:
                    source = wb_analysis[sheet_name]
                    target = wb.create_sheet(f"ANÁLISE_{sheet_name[:20]}")
                    for row in source:
                        for cell in row:
                            target.cell(row=cell.row, column=cell.column, value=cell.value)
                            if cell.has_style:
                                target.cell(row=cell.row, column=cell.column).font = copy(cell.font)
                                target.cell(row=cell.row, column=cell.column).fill = copy(cell.fill)
            except Exception as e:
                logger.error(f"Erro ao copiar análise: {e}")

    # Retorno
    out = io.BytesIO()
    wb.save(out)
    return {'excel_data': out.getvalue()}