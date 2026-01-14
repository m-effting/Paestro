import io
import logging
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_consolidated_report(chamada_files, analise_files):
    # Função legada para compatibilidade
    pass

def generate_analysis_excel(data_rows, show_monthly_details=True): 
    """
    Gera Excel com os alunos filtrados (não Regulares).
    A regra é clara: Alunos com status apenas "Regular" NÃO devem aparecer no relatório,
    mesmo que o filtro da interface esteja em "Todos".
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Análise de Faltas"
    
    # --- FILTRAGEM ---
    # Mantém apenas alunos que NÃO têm status "Regular"
    filtered_rows = []
    for row in data_rows:
        raw_status = row.get('status', [])
        status_list = []
        
        # Normalização do status para lista
        if isinstance(raw_status, str):
            status_list = [s.strip() for s in raw_status.split(',')]
        elif isinstance(raw_status, list):
            status_list = [str(s).strip() for s in raw_status]
        
        # Lógica de Exclusão Estrita:
        # 1. Se lista vazia -> Ignora (assume regular)
        # 2. Se lista tem apenas "Regular" -> Ignora
        if not status_list:
            continue
            
        if len(status_list) == 1 and status_list[0].upper() == "REGULAR":
            continue
            
        filtered_rows.append(row)
    
    # Se não sobrar ninguém (todos eram regulares ou lista vazia)
    if not filtered_rows:
        ws['A1'] = "Nenhum aluno com excesso de faltas encontrado."
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return out

    # 1. Cabeçalho Geral
    escolas = set(r.get('escola', 'N/A') for r in filtered_rows)
    escolas_str = ", ".join(sorted(list(escolas)))
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    ws['A1'] = f"Escola(s): {escolas_str}"
    ws['A1'].font = Font(bold=True, size=12)
    ws['A2'] = f"Data/Hora: {data_hora}"
    
    current_row = 4
    
    # 2. Agrupamento
    dados_por_turma = {}
    for row in filtered_rows:
        turma = row.get('turma', 'Turma Desconhecida')
        if turma not in dados_por_turma: dados_por_turma[turma] = []
        dados_por_turma[turma].append(row)
        
    sorted_turmas = sorted(dados_por_turma.keys())
    
    # Definição Dinâmica de Cabeçalhos
    headers = [
        "Aluno", "Status", "% Presença", "% FJ", "Total P", "Total F", "Total FJ"
    ]
    
    if show_monthly_details:
        headers.append("F por mês")
        
    headers.extend(["Nºs de contato", "Data do contato", "Motivo das faltas"])
    
    # Estilos
    header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    turma_fill = PatternFill(start_color="B4C6E7", end_color="B4C6E7", fill_type="solid")
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    for turma in sorted_turmas:
        # Título da Turma
        ws.cell(row=current_row, column=1, value=f"Turma: {turma}")
        ws.cell(row=current_row, column=1).font = Font(bold=True)
        ws.cell(row=current_row, column=1).fill = turma_fill
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(headers))
        current_row += 1
        
        # Cabeçalhos das Colunas
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=h)
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
        current_row += 1
        
        # Alunos
        alunos = sorted(dados_por_turma[turma], key=lambda x: x.get('aluno', ''))
        for aluno in alunos:
            # Formatações
            f_mes = aluno.get('faltas_por_mes_texto', '')
            if not f_mes and aluno.get('faltas_por_mes'):
                if isinstance(aluno['faltas_por_mes'], dict):
                    f_mes = " ".join([f"{k}:{v}" for k,v in sorted(aluno['faltas_por_mes'].items()) if v > 0])
            
            status_val = aluno.get('status', [])
            if isinstance(status_val, list): status_val = ", ".join(status_val)
            
            # Monta lista de valores
            vals = [
                aluno.get('aluno', ''),
                status_val,
                f"{aluno.get('percentual_presenca', 0)}%",
                f"{aluno.get('percentual_justificado', 0)}%",
                aluno.get('P', 0),
                aluno.get('F', 0),
                aluno.get('FJ', 0)
            ]
            
            if show_monthly_details:
                vals.append(f_mes or "N/A")
                
            vals.extend(["", "", ""]) # Campos de contato vazios
            
            for col_idx, val in enumerate(vals, 1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.border = border
                # Centraliza colunas numéricas (índices 3 a 7)
                if col_idx > 2 and col_idx < 8: 
                    cell.alignment = Alignment(horizontal='center')
            
            current_row += 1
        current_row += 1 # Espaço entre turmas
        
    # Largura das colunas
    widths = [40, 25, 12, 12, 8, 8, 8]
    if show_monthly_details:
        widths.append(35)
    widths.extend([20, 20, 40])
    
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out