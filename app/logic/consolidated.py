import pandas as pd
import re
import os
import logging
import unicodedata
from io import BytesIO
from datetime import datetime
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Imports para PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

def make_hash_key(text):
    """
    Cria uma chave única simplificada.
    Remove acentos, espaços, pontuação e caracteres especiais.
    Mantém apenas LETRAS e NÚMEROS.
    """
    if not text or pd.isna(text): return ""
    text_str = str(text)
    normalized = unicodedata.normalize('NFD', text_str)
    shaved = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    shaved = shaved.upper()
    return re.sub(r'[^A-Z0-9]', '', shaved)

def clean_display_text(text):
    """Limpa texto apenas para exibição bonita no Excel."""
    if not text or pd.isna(text): return ""
    return str(text).strip().upper().replace('\xa0', ' ').replace('  ', ' ')

def generate_pdf_bytes(school_name, monitor_rows):
    """
    Gera o PDF oficial de encaminhamento de alunos prioritários.
    Retorna um buffer de bytes com o PDF.
    """
    buffer = BytesIO()
    # Margens reduzidas para 1cm para aproveitar melhor a largura da folha
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1*cm, leftMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    story = []

    # --- Estilos Personalizados ---
    style_header_right = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        alignment=2, # 0=Left, 1=Center, 2=Right
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold'
    )
    
    style_title_left = ParagraphStyle(
        'TitleLeft',
        parent=styles['Normal'],
        alignment=0,
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold'
    )

    style_normal = ParagraphStyle(
        'MyNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        spaceAfter=6
    )

    style_list = ParagraphStyle(
        'MyList',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        leftIndent=20,
        spaceAfter=3
    )
    
    # Estilo para texto dentro da tabela
    style_table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        alignment=0 # Left
    )

    style_table_center = ParagraphStyle(
        'TableCenter',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        alignment=1 # Center
    )

    # --- Cabeçalho Direito ---
    header_text = """
    PREFEITURA DE PALHOÇA<br/>
    SECRETARIA MUNICIPAL DE EDUCAÇÃO<br/>
    CENTRAL DE MATRÍCULAS
    """
    story.append(Paragraph(header_text, style_header_right))
    story.append(Spacer(1, 1*cm))

    # --- Conteúdo Inicial ---
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    content_block_1 = f"""
    Data: {current_date}.<br/>
    À Direção da Escola: {school_name}.<br/>
    Assunto: Encaminhamento de alunos prioritários para busca ativa.
    """
    story.append(Paragraph(content_block_1, style_title_left))
    story.append(Spacer(1, 0.5*cm))

    text_body = """
    Prezada Direção,<br/><br/>
    Com base nos dados mais recentes coletados pelo Projeto Paestro, identificamos alunos faltosos nas
    analises de presença. Solicitamos, por gentileza, que seja realizada busca ativa junto às famílias para
    verificar os motivos das ausências e promover o retorno às aulas ou as devidas ações.<br/><br/>
    Segue abaixo a lista de alunos prioritários:
    """
    story.append(Paragraph(text_body, style_normal))
    story.append(Spacer(1, 0.5*cm))

    # --- Tabela ---
    headers = [
        Paragraph('<b>Turma</b>', style_table_text),
        Paragraph('<b>Aluno</b>', style_table_text),
        Paragraph('<b>Visitas</b>', style_table_center),
        Paragraph('<b>% Freq. Geral</b>', style_table_center),
        Paragraph('<b>Motivo/Providência</b>', style_table_text)
    ]
    table_data = [headers]

    rows_added = 0
    if monitor_rows:
        for row in monitor_rows:
            # 1. Lógica de Filtragem para PDF
            st_upper = str(row.get('Status', '')).upper()
            
            # Verifica Status Prioritário (Incluindo "Faltou Visitas")
            is_priority_status = "FALTOSO" in st_upper or "MUITAS FJS" in st_upper or "FALTOU VISITAS" in st_upper
            
            # Verifica se faltou em todos os dias E se o total de dias é >= 4 (redundância de segurança)
            faltas_str = str(row.get('Faltas', '0/0'))
            is_full_absence = False
            try:
                if '/' in faltas_str:
                    num, den = faltas_str.split('/')
                    # AQUI: Garante que só considera falta total se for 4/4, 5/5 ou maior.
                    if num == den and int(den) >= 4:
                        is_full_absence = True
            except: pass

            # Se não for nem status prioritário nem falta total (>=4), pula
            if not (is_priority_status or is_full_absence):
                continue

            rows_added += 1

            # 2. Lógica da Coluna % Freq. Geral
            # Pega o percentual base que já vem com as datas (ex: "0% (01/02 - 05/02)" ou "-")
            perc_display = str(row.get('Percent', ''))
            
            # Adiciona o status DEPOIS dos parênteses (ou do hífen) APENAS se for status prioritário
            if is_priority_status:
                # Recupera o status original para exibição
                raw_status = row.get('Status', '')
                perc_display = f"{perc_display} <b>{raw_status}</b>"
            
            # Cria Paragraphs
            turma_p = Paragraph(str(row.get('Turma', '')), style_table_text)
            aluno_p = Paragraph(str(row.get('Aluno', '')), style_table_text)
            faltas_p = Paragraph(faltas_str, style_table_center)
            perc_p = Paragraph(perc_display, style_table_center)
            
            line = [
                turma_p,
                aluno_p,
                faltas_p,
                perc_p,
                '' # Coluna vazia para preenchimento manual
            ]
            table_data.append(line)

    if rows_added == 0:
        table_data.append(['-', 'Nenhum aluno prioritário identificado conforme critérios.', '-', '-', '-'])

    # Configuração da Tabela
    # Largura total disponível A4 (21cm) - Margens (2cm total) = 19cm útil
    col_widths = [2.0*cm, 5.5*cm, 2.0*cm, 4.5*cm, 5.0*cm]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # --- Solicitação Final ---
    solicitacao_title = "<b>Solicitação</b>"
    story.append(Paragraph(solicitacao_title, style_normal))
    
    intro_sol = "Pedimos que a escola:"
    story.append(Paragraph(intro_sol, style_normal))

    items = [
        "1. Realize contato com os responsáveis pelos alunos listados;",
        "2. Verifique os motivos das ausências;",
        "3. Informar os motivos identificados para as ausências e as providências que serão adotadas para evitar novas faltas por parte dos alunos.",
        "4. Informe este setor em caso de necessidade de apoio adicional.",
        "5. Entregue os motivos e providências citados no 3º item dentro de sete dias úteis."
    ]

    for item in items:
        story.append(Paragraph(item, style_list))

    story.append(Spacer(1, 1.5*cm))

    # --- Assinatura ---
    footer_text = """
    SECRETARIA MUNICIPAL DE EDUCAÇÃO<br/>
    Central de Matrículas<br/>
    PAESTRO.
    """
    story.append(Paragraph(footer_text, style_title_left))

    doc.build(story)
    buffer.seek(0)
    return buffer

def process_consolidated_report(file_paths):
    attendance_files = []
    analysis_file_path = None
    
    date_pattern = re.compile(r'(\d{2}-\d{2}-\d{2,4})')
    
    # 1. Classificação
    for path in file_paths:
        filename = os.path.basename(path)
        match = date_pattern.search(filename)
        is_analysis = any(x in filename.lower() for x in ["analise", "análise", "situacao", "situação"])
        
        if match and not is_analysis:
            date_str = match.group(1)
            parts = date_str.split('-')
            if len(parts[2]) == 2: date_str = f"{parts[0]}-{parts[1]}-20{parts[2]}"
            
            attendance_files.append({
                'path': path, 
                'date': date_str, 
                'filename': filename
            })
        elif is_analysis or (not match and not analysis_file_path):
            analysis_file_path = path

    # Estruturas de Dados
    consolidated_data = {} 
    school_map = {}
    class_map = {}
    student_map = {}
    unit_annotations = {}
    all_dates = set()
    
    primary_school_hash = None 
    primary_school_name = "Escola Não Identificada"

    # ==========================================================================
    # 2. PROCESSAMENTO DAS CHAMADAS
    # ==========================================================================
    for att_file in attendance_files:
        try:
            df = pd.read_excel(att_file['path'], header=None, engine='openpyxl')
            file_school_hash = None
            
            for index, row in df.iterrows():
                row_vals = [str(x).strip() for x in row.values if pd.notna(x)]
                row_str = " ".join(row_vals).upper()
                
                if "UNIDADE:" in row_str:
                    for val in row_vals:
                        if val.upper().replace(":", "") != "UNIDADE" and len(val) > 3:
                            display = clean_display_text(val)
                            h_school = make_hash_key(display)
                            file_school_hash = h_school
                            
                            if not primary_school_hash:
                                primary_school_hash = h_school
                                primary_school_name = display
                                school_map[h_school] = display
                                if h_school not in consolidated_data: consolidated_data[h_school] = {}
                                if h_school not in unit_annotations: unit_annotations[h_school] = {}
                            break
                if file_school_hash: break 
            
            if not primary_school_hash:
                primary_school_hash = "ESCOLA_GENERICA"
                primary_school_name = "Unidade Escolar"
                school_map[primary_school_hash] = primary_school_name
                consolidated_data[primary_school_hash] = {}
                unit_annotations[primary_school_hash] = {}
            
            curr_school_hash = primary_school_hash
            
            curr_class_hash = None
            idx_aluno = -1
            idx_presenca = -1
            idx_obs = -1
            
            for index, row in df.iterrows():
                row_vals = [str(x).strip() for x in row.values if pd.notna(x)]
                row_str = " ".join(row_vals).upper()
                
                if "•" in row_str:
                    date_key = att_file['date']
                    if date_key not in unit_annotations[curr_school_hash]:
                        unit_annotations[curr_school_hash][date_key] = []
                    clean_note = clean_display_text(row_str)
                    if clean_note not in unit_annotations[curr_school_hash][date_key]:
                        unit_annotations[curr_school_hash][date_key].append(clean_note)

                row_hashes = [make_hash_key(x) for x in row.values if pd.notna(x)]
                if "ALUNO" in row_hashes and ("PRESENCA" in row_hashes or "PRESENÇA" in row_hashes):
                    idx_aluno = -1; idx_presenca = -1; idx_obs = -1
                    for i, cell in enumerate(row.values):
                        h_val = make_hash_key(cell)
                        if h_val == "ALUNO": idx_aluno = i
                        elif h_val in ["PRESENCA", "PRESENÇA"]: idx_presenca = i
                        elif "OBSERVA" in h_val: idx_obs = i
                    continue 

                if "TURMA:" in row_str:
                    raw_turma = ""
                    for val in row_vals:
                        if "TURMA:" in val.upper():
                            parts = val.upper().split("TURMA:")
                            if len(parts) > 1 and parts[1].strip():
                                raw_turma = parts[1].strip()
                                break
                    if not raw_turma:
                        try:
                            orig_row = list(row.values)
                            for i, c in enumerate(orig_row):
                                if isinstance(c, str) and "TURMA:" in c.upper():
                                    if i+1 < len(orig_row) and pd.notna(orig_row[i+1]):
                                        raw_turma = str(orig_row[i+1]).strip()
                                        break
                        except: pass

                    if raw_turma:
                        display_class = clean_display_text(raw_turma)
                        h_class = make_hash_key(display_class)
                        curr_class_hash = h_class
                        if h_class not in class_map: class_map[h_class] = display_class
                        if h_class not in consolidated_data[curr_school_hash]:
                            consolidated_data[curr_school_hash][h_class] = {}

                if curr_class_hash and idx_aluno != -1 and idx_presenca != -1:
                    try:
                        raw_aluno = row.iloc[idx_aluno]
                        raw_status = row.iloc[idx_presenca]
                        
                        if pd.notna(raw_aluno) and pd.notna(raw_status):
                            display_aluno = clean_display_text(raw_aluno)
                            h_aluno = make_hash_key(display_aluno)
                            
                            if h_aluno in ["ALUNO", "NOME", ""] or "TURMA" in h_aluno: continue
                            
                            status_clean = make_hash_key(raw_status)
                            status_display = "-"
                            # CORREÇÃO: Mais flexibilidade no mapeamento do status
                            if status_clean in ["P", "PRESENTE", "PRESENCA"]: status_display = "P"
                            elif status_clean in ["F", "FALTA", "AUSENTE"]: status_display = "F"
                            elif status_clean in ["FJ", "JUSTIFICADA"]: status_display = "FJ"
                            
                            if status_display != "-":
                                if h_aluno not in student_map: student_map[h_aluno] = display_aluno
                                
                                if h_aluno not in consolidated_data[curr_school_hash][curr_class_hash]:
                                    consolidated_data[curr_school_hash][curr_class_hash][h_aluno] = {
                                        'dates': {}, 'obs': []
                                    }
                                
                                consolidated_data[curr_school_hash][curr_class_hash][h_aluno]['dates'][att_file['date']] = status_display
                                all_dates.add(att_file['date'])
                                
                                if idx_obs != -1:
                                    raw_obs = row.iloc[idx_obs]
                                    if pd.notna(raw_obs):
                                        obs_txt = str(raw_obs).strip()
                                        if obs_txt and obs_txt.lower() != "nan":
                                            short_date = att_file['date'][:5]
                                            consolidated_data[curr_school_hash][curr_class_hash][h_aluno]['obs'].append(f"[{short_date}] {obs_txt}")

                    except IndexError: pass

        except Exception as e:
            logger.error(f"Erro ao ler arquivo {att_file['filename']}: {e}")

    sorted_dates = sorted(list(all_dates), key=lambda x: datetime.strptime(x, "%d-%m-%Y"))
    
    # Determina o período global das visitas para fallback
    visit_period_fallback = ""
    if sorted_dates:
        visit_period_fallback = f"({sorted_dates[0][:5]} - {sorted_dates[-1][:5]})"

    # ==========================================================================
    # 3. LEITURA DE DADOS DE ANÁLISE
    # ==========================================================================
    analysis_data_map = {} 
    
    if analysis_file_path:
        try:
            xls = pd.ExcelFile(analysis_file_path, engine='openpyxl')
            sheet_name = next((s for s in xls.sheet_names if "ANÁLISE" in s.upper() or "ANALISE" in s.upper()), None)
            
            if sheet_name:
                df_ana = pd.read_excel(analysis_file_path, sheet_name=sheet_name, header=None, engine='openpyxl')
                curr_ana_class_hash = None
                
                for idx, row in df_ana.iterrows():
                    row_txt = " ".join([str(x) for x in row.values if pd.notna(x)])
                    
                    if "TURMA:" in row_txt.upper():
                        parts = row_txt.upper().split("TURMA:")
                        if len(parts) > 1:
                            curr_ana_class_hash = make_hash_key(parts[1])
                        continue
                    
                    if "MÉDIA GERAL" in row_txt.upper() or "ALUNO" in row_txt.upper(): continue
                    
                    if curr_ana_class_hash and pd.notna(row[0]):
                        h_aluno = make_hash_key(row[0])
                        if h_aluno == "ALUNO": continue
                        
                        if len(row) > 2:
                            st = str(row[1]).strip()
                            pc = str(row[2]).strip()
                            if any(x in st for x in ['Faltoso', 'Monitorar', 'Regular', 'Abandono', 'Ativo']):
                                key = (curr_ana_class_hash, h_aluno)
                                analysis_data_map[key] = {'status': st, 'percent': pc}
        except Exception as e:
            logger.error(f"Erro lendo analise: {e}")

    # ==========================================================================
    # 4. GERAÇÃO DO ARQUIVO FINAL
    # ==========================================================================
    
    if analysis_file_path:
        try: wb = load_workbook(analysis_file_path)
        except: wb = Workbook()
    else: wb = Workbook()

    # --- ABA CHAMADAS ---
    if "CHAMADAS" in wb.sheetnames: del wb["CHAMADAS"]
    ws_chamadas = wb.create_sheet("CHAMADAS", 0)
    
    bold_font = Font(bold=True)
    white_font = Font(bold=True, color="FFFFFF")
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    wrap_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    
    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fill_red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    
    font_green = Font(color="006100")
    font_red = Font(color="9C0006")
    font_yellow = Font(color="9C6500")
    
    row_idx = 1
    ws_chamadas.cell(row=row_idx, column=1, value=f"RELATÓRIO CONSOLIDADO - {primary_school_name}").font = Font(bold=True, size=14)
    row_idx += 2
    
    for h_school in sorted(consolidated_data.keys()):
        if h_school in unit_annotations and unit_annotations[h_school]:
            ws_chamadas.cell(row=row_idx, column=1, value="ANOTAÇÕES DA UNIDADE:").font = bold_font
            row_idx += 1
            def date_sorter(d):
                try: return datetime.strptime(d, "%d-%m-%Y")
                except: return datetime.min
            seen_notes = set()
            for d_key in sorted(unit_annotations[h_school].keys(), key=date_sorter):
                notes = unit_annotations[h_school][d_key]
                for n in notes:
                    clean_n = str(n).replace("•", "").strip()
                    note_unique = f"{d_key}|{clean_n}"
                    if note_unique not in seen_notes and clean_n:
                        ws_chamadas.cell(row=row_idx, column=1, value=f"({d_key}) {clean_n}")
                        row_idx += 1
                        seen_notes.add(note_unique)
            row_idx += 1
        
        turmas_sorted = sorted(consolidated_data[h_school].keys())
        for h_class in turmas_sorted:
            display_class_name = class_map.get(h_class, h_class)
            cell_turma = ws_chamadas.cell(row=row_idx, column=1, value=f"TURMA: {display_class_name}")
            cell_turma.font = white_font
            cell_turma.fill = header_fill
            row_idx += 1
            
            headers = ["ALUNO"] + sorted_dates + ["Observações"]
            for c, val in enumerate(headers, 1):
                cell = ws_chamadas.cell(row=row_idx, column=c, value=val)
                cell.font = bold_font
                cell.alignment = center_align
                cell.border = border
                letter = get_column_letter(c)
                if c == 1: ws_chamadas.column_dimensions[letter].width = 40
                elif c == len(headers): ws_chamadas.column_dimensions[letter].width = 50
                else: ws_chamadas.column_dimensions[letter].width = 12
            row_idx += 1
            
            alunos_sorted = sorted(consolidated_data[h_school][h_class].keys())
            for h_aluno in alunos_sorted:
                display_aluno_name = student_map.get(h_aluno, h_aluno)
                data_dict = consolidated_data[h_school][h_class][h_aluno]
                c_nome = ws_chamadas.cell(row=row_idx, column=1, value=display_aluno_name)
                c_nome.border = border
                c_nome.alignment = left_align
                
                for d_i, date_key in enumerate(sorted_dates, 2):
                    status = data_dict['dates'].get(date_key, "-")
                    c_st = ws_chamadas.cell(row=row_idx, column=d_i, value=status)
                    c_st.alignment = center_align
                    c_st.border = border
                    if status == 'P':
                        c_st.fill = fill_green
                        c_st.font = font_green
                    elif status == 'F':
                        c_st.fill = fill_red
                        c_st.font = font_red
                    elif status == 'FJ':
                        c_st.fill = fill_yellow
                        c_st.font = font_yellow
                
                obs_final = " | ".join(data_dict['obs'])
                c_obs = ws_chamadas.cell(row=row_idx, column=len(headers), value=obs_final)
                c_obs.border = border
                c_obs.alignment = wrap_align
                row_idx += 1
            row_idx += 2

    # --- ABA MONITORAR ---
    if "MONITORAR" in wb.sheetnames: del wb["MONITORAR"]
    ws_mon = wb.create_sheet("MONITORAR")
    
    monitor_rows = []
    for h_school, turmas in consolidated_data.items():
        for h_class, alunos in turmas.items():
            for h_aluno, data_dict in alunos.items():
                frequencias = data_dict['dates']
                dias_com_registro = sum(1 for d in sorted_dates if frequencias.get(d) in ['P', 'F', 'FJ'])
                total_faltas = sum(1 for d in sorted_dates if frequencias.get(d) == 'F')
                total_dias = dias_com_registro if dias_com_registro > 0 else len(sorted_dates)
                faltas_str = f"{total_faltas}/{total_dias}"
                
                # Verifica condição "Faltou Visitas" (Faltou em TODOS os dias registrados da visita E pelo menos 4 visitas)
                # AQUI ESTÁ A LÓGICA DE NEGÓCIO PRINCIPAL PARA O EXCEL
                faltou_todas_visitas = (dias_com_registro >= 4 and total_faltas == dias_com_registro)

                ana_info = analysis_data_map.get((h_class, h_aluno))
                
                st = ""
                pc = ""
                st_display = ""
                
                if ana_info:
                    st = ana_info['status']
                    pc = ana_info['percent']
                    st_display = st
                    
                    if faltou_todas_visitas:
                        st_display = f"{st} - Faltou Visitas"
                elif faltou_todas_visitas:
                    # Aluno Regular (não está na análise) mas faltou tudo (>=4 visitas)
                    st = "Regular" # Status base implícito
                    st_display = "Faltou Visitas"
                    pc = "-"
                
                # Se não tem status definido para exibição (não é prioritário nem faltou visitas), pula
                if not st_display:
                    continue

                st_upper = st_display.upper()
                
                include = False
                prio = 0
                
                if "ABANDONO" in st_upper: include = True; prio = 100
                elif "FALTOSO" in st_upper: include = True; prio = 80
                elif "MUITAS FJS" in st_upper: include = True; prio = 80
                elif "FALTOU VISITAS" in st_upper: include = True; prio = 75 # Prioridade alta para os 100% faltantes
                elif "MONITORAR" in st_upper:
                    if total_faltas > 0: include = True; prio = 50
                
                if include:
                    # Lógica para adicionar o período se necessário
                    final_pc = pc
                    if pc != "-":
                        # Adiciona período se não tiver e não for status 'apenas regular' (mas aqui já filtramos)
                        if "REGULAR" not in st_upper and "(" not in pc:
                             final_pc = f"{pc} {visit_period_fallback}"
                        # Garante período para status combinados se faltar
                        elif "VISITAS" in st_upper and "(" not in pc:
                             final_pc = f"{pc} {visit_period_fallback}"

                    monitor_rows.append({
                        'Turma': class_map.get(h_class, h_class),
                        'Aluno': student_map.get(h_aluno, h_aluno),
                        'Faltas': faltas_str,
                        'RawFaltas': total_faltas,
                        'Status': st_display,
                        'Percent': final_pc,
                        'p': prio
                    })
    
    monitor_rows.sort(key=lambda x: (-x['p'], -x['RawFaltas'], x['Turma'], x['Aluno']))
    
    m_headers = ["Turma", "Aluno", "Faltas Visitas", "Status (Análise)", "% Presença"]
    for i, h in enumerate(m_headers, 1):
        c = ws_mon.cell(row=1, column=i, value=h)
        c.font = white_font
        c.fill = PatternFill(start_color="C0504D", end_color="C0504D", fill_type="solid")
        c.alignment = center_align
        ws_mon.column_dimensions[get_column_letter(i)].width = 40 if i in [2, 5] else 20
        
    for r, row_data in enumerate(monitor_rows, 2):
        ws_mon.cell(row=r, column=1, value=row_data['Turma']).alignment = center_align
        ws_mon.cell(row=r, column=2, value=row_data['Aluno']).alignment = left_align
        ws_mon.cell(row=r, column=3, value=row_data['Faltas']).alignment = center_align
        ws_mon.cell(row=r, column=4, value=row_data['Status']).alignment = center_align
        ws_mon.cell(row=r, column=5, value=row_data['Percent']).alignment = center_align

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Retorna o buffer do Excel, o nome da escola e as linhas de monitoramento para o PDF
    return output, primary_school_name, monitor_rows