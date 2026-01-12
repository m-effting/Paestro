import io
import logging
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_consolidated_report(chamada_files, analise_files):
    # Função legada para compatibilidade, se necessário
    pass

def generate_analysis_excel(data_rows):
    """
    Gera Excel bonitão no estilo do CSV de exemplo.
    FILTRA ALUNOS "REGULAR" (mostra apenas os que precisam de atenção).
    - Cabeçalho com Escola/Data
    - Agrupado por Turma
    - Colunas Extras
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Análise de Faltas"
    
    # --- FILTRAGEM ---
    # Mantém apenas alunos que NÃO têm status "Regular"
    filtered_rows = []
    for row in data_rows:
        status = row.get('status', [])
        # Se for string, converte para lista para verificar
        if isinstance(status, str):
            status = [s.strip() for s in status.split(',')]
        
        # Se status for vazio ou apenas "Regular", ignora
        if not status or (len(status) == 1 and "Regular" in status):
            continue
            
        filtered_rows.append(row)
    
    # Se não sobrar ninguém, avisa no Excel
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
    
    headers = [
        "Aluno", "Status", "% Presença", "Total P", "Total F", "Total FJ", 
        "F por mês", "Nºs de contato", "Data do contato", "Motivo das faltas"
    ]
    
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
        
        # Cabeçalhos
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
                    f_mes = " ".join([f"{k}:{v}" for k,v in aluno['faltas_por_mes'].items() if v > 0])
            
            status_val = aluno.get('status', [])
            if isinstance(status_val, list): status_val = ", ".join(status_val)
            
            vals = [
                aluno.get('aluno', ''),
                status_val,
                f"{aluno.get('percentual_presenca', 0)}%",
                aluno.get('P', 0),
                aluno.get('F', 0),
                aluno.get('FJ', 0),
                f_mes or "N/A",
                "", "", "" # Colunas vazias
            ]
            
            for col_idx, val in enumerate(vals, 1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.border = border
                if col_idx > 2 and col_idx < 7: cell.alignment = Alignment(horizontal='center')
            
            current_row += 1
        current_row += 1 # Espaço entre turmas
        
    # Largura das colunas
    widths = [40, 20, 12, 8, 8, 8, 35, 20, 20, 40]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out