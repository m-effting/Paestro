import logging
import re
from collections import defaultdict
from bs4 import BeautifulSoup

# Configure o logger
logger = logging.getLogger('paestro')

def determine_education_type(class_name):
    """
    Determina o tipo de educação: obrigatória (fundamental) ou não obrigatória (infantil).
    
    Esta função classifica conforme as regras:
    - Ensino infantil: GT0 ao GT5
    - Ensino fundamental: 1º ao 9º ano
    - Ensino não obrigatório: GT0 ao GT3
    - Ensino obrigatório: GT4, GT5 e 1º ao 9º ano
    
    Args:
        class_name (str): Nome da turma
        
    Returns:
        dict: Dicionário com as seguintes chaves:
              - 'nivel': "infantil" (GT0-GT5) ou "fundamental" (1º-9º)
              - 'obrigatorio': True (para GT4, GT5, 1º-9º) ou False (para GT0-GT3)
    """
    import re
    
    if not class_name:
        return {"nivel": "infantil", "obrigatorio": False}  # Default para não obrigatória
        
    class_name = class_name.upper().strip()
    
    # Inicializa o resultado
    result = {}
    
    # Detecta turmas do formato GT com números (GT0-GT5)
    gt_match = re.search(r'GT\s*([0-5])', class_name)
    if gt_match:
        gt_num = int(gt_match.group(1))
        result["nivel"] = "infantil"  # Todas as turmas GT são do nível infantil
        result["obrigatorio"] = gt_num >= 4  # GT4 e GT5 são obrigatórias
        return result
    
    # Detecta turmas do ensino fundamental (1º-9º ANO)
    ano_match = re.search(r'([1-9])(º|°|\s)?(\s)*(ANO|SERIE|SÉRIE)', class_name)
    if ano_match:
        result["nivel"] = "fundamental"
        result["obrigatorio"] = True  # Todo ensino fundamental é obrigatório
        return result
    
    # Se não conseguiu identificar, assume infantil não obrigatório
    result["nivel"] = "infantil"
    result["obrigatorio"] = False
    return result


def get_school_info(html_content, filename=None):
    """
    Extrai informações básicas da escola e turma usando somente os prefixos específicos.
    
    Args:
        html_content (str): Conteúdo HTML completo
        filename (str, optional): Nome do arquivo de origem, usado para extrair informação da turma
        
    Returns:
        dict: Dicionário com as chaves:
            - unit_name: Nome da unidade escolar
            - class_name: Nome da turma
            - school_days: Número de dias letivos (default: 0)
    """
    result = {
        'unit_name': 'Não identificada',
        'class_name': 'Não identificada',
        'school_days': 0
    }
    
    # Primeiro, tenta extrair o nome da turma do arquivo (mais confiável)
    if filename:
        # Remove extensão e caminho se presentes
        clean_filename = filename.split('/')[-1].replace('.html', '')
        
        # Padrão para turmas GT (GT5A, GT3B)
        gt_match = re.search(r'GT\s*(\d+[A-Z]?)', clean_filename.upper())
        if gt_match:
            turma_nome = f"GT{gt_match.group(1)}"
            logger.info(f"✓ Turma GT extraída do nome do arquivo: {turma_nome}")
            result['class_name'] = turma_nome
            
        # Padrão para anos (1ANO, 8ANO1, etc)
        elif not gt_match:
            ano_match = re.search(r'(\d+)[Aª]?[Nn][Oo]', clean_filename.upper())
            if ano_match:
                numero = ano_match.group(1)
                turma_nome = f"{numero}º ANO"
                logger.info(f"✓ Turma ANO extraída do nome do arquivo: {turma_nome}")
                result['class_name'] = turma_nome
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Buscar nome da unidade escolar usando apenas os prefixos específicos solicitados
        unit_name = None
        
        # Lista de prefixos específicos para identificar escolas
        prefixos_escola = [
            'EM ','CAIC ', 'EB ','EBM ','GE ', 'ER ', 'EI ', 'CENTRO ', 'CEI '
        ]
        
        # Lista de palavras proibidas para evitar pegar títulos de relatórios
        palavras_proibidas = [
            'REGISTRO GERAL', 'RELATÓRIO', 'FREQUÊNCIA', 'DIÁRIO',
            'BOLETIM', 'EDUCA', 'CHAMADA', 'EDUCAÇÃO', 'TRIMESTRE', 'SEMESTRE',
            'RELATÓRIO',  'DOCUMENTO', 'PLANILHA', 'TURMA', 'LISTAGEM'
        ]
        
        # Primeiro, procura em tabelas de cabeçalho usando apenas os prefixos específicos
        for table in soup.find_all('table')[:3]:  # Primeiras 3 tabelas (geralmente cabeçalho)
            if unit_name:
                break
                
            for row in table.find_all('tr')[:4]:  # Primeiras 4 linhas
                if unit_name:
                    break
                    
                for cell in row.find_all('td'):
                    text = cell.get_text().strip()
                    text_upper = text.upper()
                    
                    # Verifica se o texto começa com algum dos prefixos específicos
                    if any(text_upper.startswith(prefixo) for prefixo in prefixos_escola):
                        # Verifica se não contém palavras proibidas
                        if not any(proibida in text_upper for proibida in palavras_proibidas):
                            # Verifica se tem tamanho razoável (não é apenas uma sigla)
                            if len(text) > 10:
                                unit_name = text
                                logger.info(f"Nome da unidade identificado pelo prefixo específico em tabela: {unit_name}")
                                break
        
        # Se não encontrou em tabelas, busca em spans/divs
        if not unit_name:
            for element in soup.find_all(['span', 'div']):
                if not element.string:
                    continue
                    
                text = element.string.strip()
                text_upper = text.upper()
                
                # Verifica se o texto começa com algum dos prefixos específicos
                if any(text_upper.startswith(prefixo) for prefixo in prefixos_escola):
                    # Verifica se não contém palavras proibidas
                    if not any(proibida in text_upper for proibida in palavras_proibidas):
                        # Verifica se tem tamanho razoável (não é apenas uma sigla)
                        if len(text) > 10:
                            unit_name = text
                            logger.info(f"Nome da unidade identificado pelo prefixo específico em span/div: {unit_name}")
                            break
        
        # Se encontrou um nome de unidade, normaliza o formato
        if unit_name:
            # Limpa o nome (remove caracteres especiais e normaliza espaços)
            unit_name = re.sub(r'\s+', ' ', unit_name).strip()
            result['unit_name'] = unit_name
        
        # 2. Buscar nome da turma
        class_name = None
        
        # Inicializa dicionários para armazenar todos os candidatos a nome de turma
        turmas_encontradas = []
        
        # Primeiro vamos buscar por texto que explicitamente diz "TURMA:"
        for span in soup.find_all('span'):
            if not span.string:
                continue
                
            text = span.string.strip().upper()
            if "TURMA:" in text:
                # Se encontrou "TURMA:", verifica o próximo span ou o texto após os dois pontos
                if ":" in text:
                    # Obtém o texto após os dois pontos
                    turma_text = text.split(":", 1)[1].strip()
                    if turma_text:
                        turmas_encontradas.append({"texto": turma_text, "prioridade": 1})
                        logger.info(f"Candidato a turma (após 'TURMA:'): {turma_text}")
                else:
                    # Busca o próximo span que pode conter o nome da turma
                    next_span = span.find_next('span')
                    if next_span and next_span.string:
                        turma_text = next_span.string.strip().upper()
                        if turma_text and len(turma_text) < 30:  # Limita o tamanho para evitar textos grandes
                            turmas_encontradas.append({"texto": turma_text, "prioridade": 2})
                            logger.info(f"Candidato a turma (span após 'TURMA:'): {turma_text}")
        
        # Agora busca por padrões específicos em todos os spans
        for span in soup.find_all('span'):
            if not span.string:
                continue
                
            text = span.string.strip().upper()
            
            # Verificar se tem "GT0", "GT1", "GT2", "GT3", "GT4", "GT5" ou "ANO"
            if any(gr in text for gr in ['GT0', 'GT1', 'GT2', 'GT3', 'GT4', 'GT5']):
                # Formato GT com número e letra após: GT0 a GT5 (exemplo: GT5B)
                gt_match = re.search(r'(GT\s*[0-5])\s*(-|–|—)*\s*([A-Z0-9])?', text)
                if gt_match:
                    gt, _, letter = gt_match.groups()
                    letter = letter or ""
                    nome_turma = f"{gt.replace(' ', '')}{letter}".strip()
                    turmas_encontradas.append({"texto": nome_turma, "prioridade": 3})
                    logger.info(f"Candidato a turma (padrão GT): {nome_turma}")
            
            # Busca por ANO no texto
            if 'ANO' in text and any(ano in text for ano in ['1º', '2º', '3º', '4º', '5º', '6º', '7º', '8º', '9º', '1°', '2°', '3°', '4°', '5°', '6°', '7°', '8°', '9°']):
                # Caso explícito: 1º ANO - 3 (formato prioritário)
                explicit_match = re.search(r'(\d{1,2})(º|ª|°)?\s*ANO\s*[-–—]\s*(\d+)', text, re.IGNORECASE)
                if explicit_match:
                    num, ordinal, turma_num = explicit_match.groups()
                    nome_turma = f"{num}º ANO - {turma_num}".strip()
                    turmas_encontradas.append({"texto": nome_turma, "prioridade": 4})
                    logger.info(f"Candidato a turma (ANO com número após hífen): {nome_turma}")
                
                # Verifica letra após ANO: 1º ANO A
                ano_letter_match = re.search(r'(\d{1,2})(º|ª|°)?\s*ANO\s*([A-Z])', text, re.IGNORECASE)
                if ano_letter_match:
                    num, ordinal, letter = ano_letter_match.groups()
                    nome_turma = f"{num}º ANO {letter}".strip()
                    turmas_encontradas.append({"texto": nome_turma, "prioridade": 5})
                    logger.info(f"Candidato a turma (ANO com letra): {nome_turma}")
                
                # Se ainda não encontrou um padrão com número/letra, pega apenas o número do ano
                if not explicit_match and not ano_letter_match:
                    ano_match = re.search(r'(\d{1,2})(º|ª|°)?\s*ANO', text, re.IGNORECASE)
                    if ano_match:
                        num, ordinal = ano_match.groups()
                        nome_turma = f"{num}º ANO".strip()
                        turmas_encontradas.append({"texto": nome_turma, "prioridade": 6})
                        logger.info(f"Candidato a turma (apenas número do ano): {nome_turma}")
        
        # Agora verifica se alguma turma tipo "3º ANO" precisa ser complementada com um número após o hífen
        # que pode estar em outro lugar no texto
        for i, turma in enumerate(turmas_encontradas):
            if 'ANO' in turma['texto'] and ' - ' not in turma['texto'] and ' A' not in turma['texto'] and ' B' not in turma['texto']:
                num_ano_match = re.search(r'(\d{1,2})º ANO', turma['texto'])
                if num_ano_match:
                    num_ano = num_ano_match.group(1)
                    
                    # MÉTODO 1: Busca diretamente no HTML completo
                    # Este método é mais eficaz para encontrar o padrão completo, mesmo em elementos separados
                    full_html_pattern = re.search(rf'{num_ano}[ºª°]?\s*ANO\s*[-–—]\s*(\d+)', html_content, re.IGNORECASE)
                    if full_html_pattern:
                        turma_num = full_html_pattern.group(1)
                        turmas_encontradas[i]['texto'] = f"{num_ano}º ANO - {turma_num}"
                        turmas_encontradas[i]['prioridade'] = 5  # Prioridade máxima
                        logger.info(f"Turma atualizada com número após hífen (método 1): {turmas_encontradas[i]['texto']}")
                    else:
                        # MÉTODO 2: Busca no nome do arquivo se disponível
                        if filename:
                            # Formato comum: CAIC3ANO1.html, MARA3ANO1.html (escola+série+número)
                            file_pattern = re.search(rf'{num_ano}ANO(\d+)', filename, re.IGNORECASE)
                            if file_pattern:
                                turma_num = file_pattern.group(1)
                                turmas_encontradas[i]['texto'] = f"{num_ano}º ANO - {turma_num}"
                                turmas_encontradas[i]['prioridade'] = 4  # Alta prioridade
                                logger.info(f"Turma atualizada com número após hífen (método 2): {turmas_encontradas[i]['texto']}")
                            
                        # MÉTODO 3: Busca em spans específicos (método original)
                        if turmas_encontradas[i]['prioridade'] < 4:
                            for span in soup.find_all('span'):
                                if not span.string:
                                    continue
                                    
                                text = span.string.strip().upper()
                                # Procura padrões como "3º ANO - 1" ou variações
                                dash_num_match = re.search(rf'{num_ano}[ºª°]?\s*ANO\s*[-–—]\s*(\d+)', text, re.IGNORECASE)
                                if dash_num_match:
                                    turma_num = dash_num_match.group(1)
                                    turmas_encontradas[i]['texto'] = f"{num_ano}º ANO - {turma_num}"
                                    turmas_encontradas[i]['prioridade'] = 3  # Prioridade média
                                    logger.info(f"Turma atualizada com número após hífen (método 3): {turmas_encontradas[i]['texto']}")
                                    break

        # Seleciona a turma com maior prioridade
        if turmas_encontradas:
            # Ordena pela prioridade (números menores = maior prioridade)
            turmas_ordenadas = sorted(turmas_encontradas, key=lambda x: x['prioridade'])
            class_name = turmas_ordenadas[0]['texto']
            logger.info(f"Turma selecionada com maior prioridade: {class_name}")
        else:
            class_name = None
        
        # Se encontrou um nome de turma, salva
        if class_name:
            result['class_name'] = class_name
        
        # 3. Buscar número de dias letivos
        for span in soup.find_all('span'):
            if span.string and "DIAS LETIVOS" in span.string.upper():
                # Buscar o número de dias letivos (geralmente um número próximo)
                text = span.string.upper()
                days_match = re.search(r'DIAS\s+LETIVOS\s*[:=]?\s*(\d+)', text)
                if days_match:
                    result['school_days'] = int(days_match.group(1))
                    logger.info(f"Dias letivos encontrados: {result['school_days']}")
                    break
                
                # Ou pode estar no próximo elemento span ou em uma célula próxima
                next_span = span.find_next('span')
                if next_span and next_span.string and next_span.string.strip().isdigit():
                    result['school_days'] = int(next_span.string.strip())
                    logger.info(f"Dias letivos encontrados no span seguinte: {result['school_days']}")
                    break
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao extrair informações básicas: {str(e)}")
        return result


def get_student_list(html_content):
    """
    Extrai a lista completa de alunos do documento.
    Usa múltiplos métodos para garantir que encontre os alunos em diferentes formatos de página.
    
    Args:
        html_content (str): Conteúdo HTML completo
        
    Returns:
        list: Lista de nomes de alunos encontrados
    """
    students = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # MÉTODO 1: Buscar por células marcadas como alunas em tabelas 
        # Identificar alunos por peso da fonte (geralmente em negrito)
        for span in soup.find_all('span'):
            if not span.string:
                continue
                
            # Verificar se o span tem formatação de fonte que sugere nome de aluno
            # Geralmente em negrito ou com tamanho de fonte diferente
            style = span.get('style', '').lower()
            if 'bold' in style or 'font-weight: bold' in style or 'font-size: 7px' in style or 'font-size: 8px' in style:
                student_name = span.string.strip()
                
                # Verifica se parece nome de aluno (pelo menos 2 palavras, maiúsculas)
                if len(student_name.split()) >= 2 and student_name.isupper():
                    # Remove números do nome (pode ter números de matrícula)
                    clean_name = re.sub(r'\d+', '', student_name).strip()
                    # Lista expandida de palavras-chave que NÃO são nomes de alunos
                    palavras_excluidas = [
                        'PROFESSOR', 'ALUNO', 'COMPONENTE', 'CURRICULAR', 'MUNICÍPIO', 
                        'PALHOÇA', 'CEI', 'CONVIVER', 'TOTAL', 'DIAS', 'LETIVOS',
                        'APROFUNDAMENTO', 'ENSINO', 'RELIGIOSO', 'GEOGRAFIA', 'HISTÓRIA',
                        'EDUCAÇÃO', 'FÍSICA', 'LEITURA', 'ESCRITA', 'ARTE', 'CIÊNCIAS',
                        'LÍNGUA', 'PORTUGUESA', 'ESTRANGEIRA', 'INGLÊS', 'MATEMÁTICA'
                    ]
                    # Verificação mais rigorosa para evitar textos que não são nomes
                    if (len(clean_name) > 5 and ":" not in clean_name and 
                        not any(keyword in clean_name.upper() for keyword in palavras_excluidas)):
                        students.append(clean_name)
        
        # MÉTODO 2: Buscar por células em tabelas que contenham nomes 
        # Verificar tabelas maiores que geralmente contêm a lista principal de alunos
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            # Considerar apenas tabelas com muitas linhas (provavelmente a lista de alunos)
            if len(rows) > 5:
                # Para cada linha, extrair potenciais alunos
                for row in rows[1:]:  # Pular o cabeçalho
                    cells = row.find_all('td')
                    # Pular linhas sem células
                    if not cells:
                        continue
                        
                    # Geralmente o nome do aluno está na primeira ou segunda célula
                    # Tentamos as primeiras células (até a 3ª)
                    for idx in range(min(3, len(cells))):
                        cell_text = cells[idx].get_text().strip()
                        # Verificar se parece um nome de aluno (pelo menos 2 palavras)
                        if len(cell_text.split()) >= 2 and len(cell_text) > 5:
                            # Limpar o nome
                            clean_name = re.sub(r'\d+', '', cell_text).strip()
                            # Verificar se não é um cabeçalho ou informação administrativa
                            palavras_excluidas = [
                                'TOTAL', 'PROFESSOR', 'ALUNO:', 'CURSO', 'MATRÍCULA', 'COMPONENTE', 
                                'CURRICULAR', 'MUNICÍPIO', 'PALHOÇA', 'CEI', 'CONVIVER', 'DIAS', 'LETIVOS',
                                'APROFUNDAMENTO', 'ENSINO', 'RELIGIOSO', 'GEOGRAFIA', 'HISTÓRIA',
                                'EDUCAÇÃO', 'FÍSICA', 'LEITURA', 'ESCRITA', 'ARTE', 'CIÊNCIAS',
                                'LÍNGUA', 'PORTUGUESA', 'ESTRANGEIRA', 'INGLÊS', 'MATEMÁTICA'
                            ]
                            if (not any(keyword in clean_name.upper() for keyword in palavras_excluidas) and 
                                ":" not in clean_name):
                                students.append(clean_name)
                                break  # Pula para próxima linha após encontrar um aluno
        
        # MÉTODO 3: Buscar spans que contenham nomes em ALL CAPS
        if not students:
            for span in soup.find_all('span'):
                if span.string and span.string.strip().isupper():
                    text = span.string.strip()
                    # Verificar se tem pelo menos 2 palavras e é relativamente longo
                    palavras_excluidas = [
                        'RELATÓRIO', 'TOTAL', 'PROFESSOR', 'BIMESTRE', 'SEMESTRE', 'COMPONENTE', 
                        'CURRICULAR', 'MUNICÍPIO', 'PALHOÇA', 'CEI', 'CONVIVER', 'DIAS', 'LETIVOS',
                        'APROFUNDAMENTO', 'ENSINO', 'RELIGIOSO', 'GEOGRAFIA', 'HISTÓRIA',
                        'EDUCAÇÃO', 'FÍSICA', 'LEITURA', 'ESCRITA', 'ARTE', 'CIÊNCIAS',
                        'LÍNGUA', 'PORTUGUESA', 'ESTRANGEIRA', 'INGLÊS', 'MATEMÁTICA', 'ALUNO:'
                    ]
                    if (len(text.split()) >= 2 and len(text) > 10 and 
                        not any(keyword in text for keyword in palavras_excluidas) and
                        ":" not in text):
                        # Remove números (matrículas) e adiciona
                        clean_name = re.sub(r'\d+', '', text).strip()
                        if len(clean_name) > 5:
                            students.append(clean_name)
        
        # Remover duplicatas e ordenar
        students = list(dict.fromkeys(students))
        
        logger.info(f"Encontrados {len(students)} alunos no documento")
        return students
        
    except Exception as e:
        logger.error(f"Erro ao extrair lista de alunos: {str(e)}")
        return students


def find_date_columns(soup):
    """
    Localiza colunas com datas em tabelas no formato DD/MM.
    
    Args:
        soup: Objeto BeautifulSoup do documento
        
    Returns:
        dict: Mapeamento de índices de colunas para informações de data {column_index: {'day': day, 'month': month}}
    """
    date_columns = {}
    
    # Buscar por células de cabeçalho com padrão de data DD/MM
    for th in soup.find_all(['th', 'td']):
        text = th.get_text().strip()
        date_match = re.search(r'(\d{1,2})/(\d{1,2})', text)
        if date_match and len(text) <= 8:  # Limita o comprimento para evitar falsos positivos
            day, month = int(date_match.group(1)), int(date_match.group(2))
            if 1 <= day <= 31 and 1 <= month <= 12:
                # Encontra o índice desta coluna na linha
                parent_row = th.find_parent('tr')
                if parent_row:
                    cells = parent_row.find_all(['th', 'td'])
                    try:
                        col_idx = list(cells).index(th)
                        date_columns[col_idx] = {'day': day, 'month': month}
                    except ValueError:
                        pass  # Ignora se não conseguir determinar o índice
    
    return date_columns


def is_f_mark(cell):
    """Verifica se uma célula contém uma marcação de falta ('F')"""
    # Verifica o texto do span ou da célula diretamente
    for span in cell.find_all('span'):
        if span.get_text().strip() == 'F':
            return True
    
    # Verifica o texto direto da célula (sem spans)
    if cell.get_text().strip() == 'F':
        return True
    
    return False


def is_yellow_cell(cell):
    """Verifica se uma célula tem fundo amarelo (aula não ministrada)"""
    style = cell.get('style', '').lower()
    return 'background-color:yellow' in style or 'background-color: yellow' in style


def process_student_attendance(html_content, student_name):
    """
    Processa as faltas de um aluno específico, implementando técnicas específicas
    para arquivos infantis (GT0-GT5) e do fundamental.
    
    Args:
        html_content (str): Conteúdo HTML completo
        student_name (str): Nome do aluno para buscar as faltas
        
    Returns:
        dict: Dicionário com as faltas por mês e texto formatado
    """
    result = {
        'faltas_por_mes': {},
        'faltas_por_mes_texto': '',
        'maior_falta_mensal': 0
    }
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Localiza todas as colunas com datas no documento
        date_columns = {}
        
        # MÉTODO 1: Identifica todas as colunas com datas no formato DD/MM
        date_pattern = re.compile(r'\d{1,2}/\d{1,2}')
        for header in soup.find_all(['th', 'td']):
            header_text = header.get_text().strip()
            date_match = date_pattern.search(header_text)
            if date_match and len(header_text) <= 6:  # Limite de tamanho para evitar textos longos
                try:
                    day_month = header_text.split('/')
                    if len(day_month) >= 2:
                        day = int(day_month[0])
                        month = int(day_month[1])
                        if 1 <= day <= 31 and 1 <= month <= 12:
                            date_columns[header] = {'day': day, 'month': month}
                            logger.info(f"Cabeçalho de data encontrado: {day}/{month}")
                except (ValueError, IndexError):
                    pass
        
        # Localiza as linhas que contêm o nome do aluno
        all_f_marks = []  # Lista para armazenar todas as marcações de falta com mês
        
        # MÉTODO 2: Processa cada célula 'F' diretamente nas linhas do aluno
        # e correlaciona com os cabeçalhos de datas
        student_cells = soup.find_all(text=lambda text: text and student_name in str(text))
        logger.info(f"Encontradas {len(student_cells)} ocorrências do nome do aluno")
        
        for cell in student_cells:
            student_row = cell.find_parent('tr')
            if not student_row:
                continue
                
            # Encontra todas as células na linha deste aluno
            row_cells = student_row.find_all('td')
            
            # Localiza o pai dessa linha (tabela)
            table = student_row.find_parent('table')
            if not table:
                continue
                
            # Processa cada célula da linha e verifica se tem 'F'
            for idx, td in enumerate(row_cells):
                td_text = td.get_text().strip()
                
                if td_text == 'F':
                    logger.info(f"Célula com 'F' encontrada na linha do aluno")
                    
                    # Método 2.1: Verifica se encontra um cabeçalho com data na mesma coluna
                    data_encontrada = False
                    
                    # Busca por todas as linhas de cabeçalho da tabela
                    all_rows = table.find_all('tr')
                    for header_row in all_rows:
                        # Se for a própria linha do aluno, pule
                        if header_row == student_row:
                            continue
                            
                        # Obtém todas as células deste cabeçalho
                        header_cells = header_row.find_all('td')
                        
                        # Se tiver células suficientes para acessar o mesmo índice
                        if idx < len(header_cells):
                            header_cell = header_cells[idx]
                            header_text = header_cell.get_text().strip()
                            
                            # Método 2.1.1: Verifica se essa célula diretamente tem uma data
                            date_match = date_pattern.search(header_text)
                            if date_match and len(header_text) <= 6:
                                try:
                                    day_month = header_text.split('/')
                                    if len(day_month) >= 2:
                                        day = int(day_month[0])
                                        month = int(day_month[1])
                                        if 1 <= day <= 31 and 1 <= month <= 12:
                                            all_f_marks.append({'day': day, 'month': month})
                                            logger.info(f"Data associada à falta: {day}/{month}")
                                            data_encontrada = True
                                            break
                                except (ValueError, IndexError):
                                    pass
                            
                            # Método 2.1.2: Verifica se essa célula está no mapeamento de datas
                            if not data_encontrada and header_cell in date_columns:
                                date_info = date_columns[header_cell]
                                all_f_marks.append(date_info)
                                logger.info(f"Data associada (mapeamento): {date_info['day']}/{date_info['month']}")
                                data_encontrada = True
                                break
                            
                            # Método 2.1.3: Procura spans dentro da célula do cabeçalho
                            if not data_encontrada:
                                for span in header_cell.find_all('span'):
                                    span_text = span.get_text().strip()
                                    date_match = date_pattern.search(span_text)
                                    if date_match and len(span_text) <= 6:
                                        try:
                                            day_month = span_text.split('/')
                                            if len(day_month) >= 2:
                                                day = int(day_month[0])
                                                month = int(day_month[1])
                                                if 1 <= day <= 31 and 1 <= month <= 12:
                                                    all_f_marks.append({'day': day, 'month': month})
                                                    logger.info(f"Data via span: {day}/{month}")
                                                    data_encontrada = True
                                                    break
                                        except (ValueError, IndexError):
                                            pass
                                            
                            if data_encontrada:
                                break
                    
                    # Método 2.2: Se não encontrou cabeçalho com data, busca nas células adjacentes
                    if not data_encontrada:
                        # Procura nas células adjacentes à atual por uma data
                        for i in range(max(0, idx-3), min(len(row_cells), idx+4)):
                            if i != idx:  # Não queremos a própria célula
                                adj_cell = row_cells[i]
                                adj_text = adj_cell.get_text().strip()
                                date_match = date_pattern.search(adj_text)
                                if date_match and len(adj_text) <= 6:  # Limita tamanho
                                    try:
                                        day_month = adj_text.split('/')
                                        if len(day_month) >= 2:
                                            day = int(day_month[0])
                                            month = int(day_month[1])
                                            if 1 <= day <= 31 and 1 <= month <= 12:
                                                all_f_marks.append({'day': day, 'month': month})
                                                logger.info(f"Data adjacente: {day}/{month}")
                                                data_encontrada = True
                                                break
                                    except (ValueError, IndexError):
                                        pass
        
        logger.info(f"Encontrou {len(all_f_marks)} marcações 'F' para o aluno {student_name}")
        
        # MÉTODO 3: Agrupamento das faltas por mês com validação
        from datetime import datetime
        try:
            from backend.analysis.utils import get_month_name
        except ImportError:
            # Fallback se não conseguir importar
            def get_month_name(month_number):
                month_names = {
                    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
                    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
                    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
                }
                return month_names.get(month_number, str(month_number))
        
        # Obtém data atual para validação
        data_atual = datetime.now()
        mes_atual = data_atual.month
        ano_atual = data_atual.year
        
        # Define os meses letivos (todos os meses do ano, exceto férias)
        # No Brasil, o ano letivo vai de fevereiro a dezembro, dividido em dois semestres
        # Incluímos todos os meses para não perder nenhuma falta que apareça no HTML
        meses_validos = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12]  # Excluindo apenas férias (Jan e Jul)
        
        logger.info(f"Processando faltas para os meses: {meses_validos}")
        
        # Conta as faltas por mês, considerando todos os meses do ano letivo
        faltas_por_mes = defaultdict(int)
        
        # Se não encontrou nenhuma falta, tenta novamente usando um método mais agressivo
        if len(all_f_marks) == 0:
            logger.info(f"MÉTODO ALTERNATIVO: Buscando faltas para {student_name} usando busca direta")
            
            # Busca todas as células com 'F' em toda a página
            all_f_cells = soup.find_all('td', string='F')
            
            for f_cell in all_f_cells:
                # Verifica se essa célula 'F' está em uma linha que contém o nome do aluno
                row = f_cell.find_parent('tr')
                if row and student_name in row.get_text():
                    # Encontra o índice da coluna dessa célula F
                    cells = row.find_all('td')
                    if cells:
                        try:
                            idx = list(cells).index(f_cell)
                            
                            # Busca o cabeçalho dessa coluna na tabela
                            table = row.find_parent('table')
                            if table:
                                # Procura em todas as linhas anteriores a esta
                                prev_rows = table.find_all('tr')
                                current_row_idx = list(prev_rows).index(row)
                                
                                # Verifica cada linha acima da atual em busca de datas
                                for i in range(current_row_idx):
                                    header_row = prev_rows[i]
                                    header_cells = header_row.find_all('td')
                                    
                                    # Se encontrar cabeçalho na mesma coluna
                                    if len(header_cells) > idx:
                                        header_cell = header_cells[idx]
                                        header_text = header_cell.get_text().strip()
                                        
                                        # Verifica se o texto parece uma data
                                        date_match = date_pattern.search(header_text)
                                        if date_match and len(header_text) <= 6:
                                            try:
                                                day_month = header_text.split('/')
                                                if len(day_month) >= 2:
                                                    day = int(day_month[0])
                                                    month = int(day_month[1])
                                                    if 1 <= day <= 31 and 1 <= month <= 12:
                                                        all_f_marks.append({'day': day, 'month': month})
                                                        logger.info(f"Data encontrada (método alternativo): {day}/{month}")
                                            except (ValueError, IndexError):
                                                pass
                        except (ValueError, IndexError):
                            pass
        
        # Verifica se estamos lidando com ensino fundamental
        is_fundamental = determine_education_type(get_school_info(html_content).get('class_name', '')).get('nivel') == 'fundamental'
        
        # Para ensino fundamental, tratamento especial para não contar múltiplas faltas no mesmo dia
        if is_fundamental:
            # Agrupa as faltas por dia/mês para evitar duplicidades no mesmo dia
            faltas_por_dia = {}  # Chave: "mes-dia", valor: quantidade de faltas
            
            # Primeiro, identifica quantas disciplinas têm por dia
            for mark in all_f_marks:
                if 'month' in mark and 'day' in mark:
                    month = mark['month']
                    day = mark['day']
                    day_key = f"{month}-{day}"
                    
                    if day_key not in faltas_por_dia:
                        faltas_por_dia[day_key] = 0
                    faltas_por_dia[day_key] += 1
            
            # Calcula o total de faltas por mês, contando cada dia apenas uma vez
            dias_com_falta_por_mes = {}
            for day_key, count in faltas_por_dia.items():
                month = int(day_key.split('-')[0])
                if month in meses_validos:
                    if month not in dias_com_falta_por_mes:
                        dias_com_falta_por_mes[month] = 0
                    # Considera como falta se perdeu mais da metade das aulas do dia
                    # ou pelo menos uma aula, dependendo da política da escola
                    dias_com_falta_por_mes[month] += 1
            
            # Atualiza a contagem de faltas por mês
            for month, count in dias_com_falta_por_mes.items():
                faltas_por_mes[month] = count
                logger.info(f"Ensino fundamental: {count} dias com falta no mês {month} ({get_month_name(month)})")
        else:
            # Para ensino infantil, contagem normal de faltas
            for mark in all_f_marks:
                if 'month' in mark:
                    month = mark['month']
                    # Conta todos os meses válidos, mesmo os que já passaram
                    if month in meses_validos:
                        faltas_por_mes[month] += 1
                        logger.info(f"Falta contabilizada para mês {month} ({get_month_name(month)})")
                    else:
                        logger.info(f"Falta ignorada para mês {month} - não é um mês letivo válido")
        
        # Passo 4: Formata o resultado com nomes de meses (Jan, Fev, Mar)
        if faltas_por_mes:
            # Convertemos os números dos meses para nomes abreviados (Jan, Fev)
            faltas_texto = []
            for month, count in sorted(faltas_por_mes.items()):
                # Converte número do mês para abreviação (Jan, Fev, Mar)
                month_name = get_month_name(month)
                faltas_texto.append(f"{month_name}:{count}")
            
            # Criar um dicionário onde a chave é o nome do mês (Jan, Fev) e não o número
            faltas_por_mes_formatado = {}
            for month, count in faltas_por_mes.items():
                month_name = get_month_name(month)
                faltas_por_mes_formatado[month_name] = count
            
            # Salvar os dois formatos - numérico para processamento e texto para exibição
            result['faltas_por_mes'] = dict(faltas_por_mes)  # Formato numérico (1, 2, 3...)
            result['faltas_por_mes_nome'] = faltas_por_mes_formatado  # Formato texto (Jan, Fev, Mar...)
            result['faltas_por_mes_texto'] = " ".join(faltas_texto)  # String formatada para exibição
            result['maior_falta_mensal'] = max(faltas_por_mes.values()) if faltas_por_mes else 0
            
            logger.info(f"Faltas por mês para {student_name}: {result['faltas_por_mes_texto']}")
            logger.info(f"Maior falta mensal: {result['maior_falta_mensal']}")
        else:
            # Se não encontrou faltas, mantém valores padrão (vazios)
            result['faltas_por_mes_texto'] = "Sem faltas"
            result['faltas_por_mes_nome'] = {}  # Dicionário vazio com nomes de meses
            result['maior_falta_mensal'] = 0
            logger.info(f"Não foram encontradas faltas para {student_name}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao processar faltas para {student_name}: {str(e)}")
        logger.exception(e)
        return result


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
    import re
    from bs4 import BeautifulSoup
    import logging
    
    logger = logging.getLogger('paestro')
    
    # Resultado padrão (zeros)
    result = {'P': 0, 'F': 0, 'FJ': 0, 'Tipo': 'Normal'}
    
    # Verifica se o conteúdo HTML é válido
    if not html_content or len(html_content) < 100:
        logger.warning(f"HTML inválido ao buscar totais para {student_name}")
        return result
    
    # Parseia o HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    try:
        # PASSO 1: Encontrar todas as tabelas de totais que contém P, F, FJ
        # Pode haver várias tabelas de totais em arquivos grandes
        p_headers = soup.find_all('span', string='P')
        f_headers = soup.find_all('span', string='F')
        fj_headers = soup.find_all('span', string='FJ')
        
        # Lista para armazenar todas as tabelas de totais encontradas
        pfj_tables = []
        
        for p_header in p_headers:
            parent_td = p_header.find_parent('td')
            if not parent_td:
                continue
            
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
                            p_idx = row_cells.index(parent_td)
                            f_idx = row_cells.index(next_td)
                            fj_idx = row_cells.index(next_next_td)
                            
                            pfj_tables.append({
                                'table': header_table,
                                'header_row': header_row,
                                'p_idx': p_idx,
                                'f_idx': f_idx,
                                'fj_idx': fj_idx
                            })
                        except ValueError as e:
                            logger.error(f"Erro ao determinar índices das colunas P, F, FJ: {str(e)}")
                            continue
        
        logger.info(f"Encontradas {len(pfj_tables)} tabelas de totais com colunas P, F, FJ")
        
        if not pfj_tables:
            logger.warning(f"Não foi possível encontrar tabelas de totais para {student_name}")
            # Não há mais mapeamento, então retorna zeros
            logger.info(f"Nenhuma tabela de totais encontrada para {student_name}, retornando valores padrão")
            return result
        
        # PASSO 2: Para cada tabela de totais, procurar o aluno e extrair os valores
        for table_info in pfj_tables:
            table = table_info['table']
            header_row = table_info['header_row']
            p_idx = table_info['p_idx']
            f_idx = table_info['f_idx']
            fj_idx = table_info['fj_idx']
            
            # Encontrar todas as linhas após o cabeçalho
            student_rows = []
            found_header = False
            for tr in table.find_all('tr'):
                if tr == header_row:
                    found_header = True
                    continue
                
                if found_header and student_name in tr.get_text():
                    student_rows.append(tr)
            
            if student_rows:
                # Pegar a linha do aluno
                student_row = student_rows[-1]
                cells = student_row.find_all('td')
                
                # Extrair os valores P, F, FJ
                if p_idx < len(cells) and cells[p_idx].get_text().strip().isdigit():
                    result['P'] = int(cells[p_idx].get_text().strip())
                if f_idx < len(cells) and cells[f_idx].get_text().strip().isdigit():
                    result['F'] = int(cells[f_idx].get_text().strip())
                if fj_idx < len(cells) and cells[fj_idx].get_text().strip().isdigit():
                    result['FJ'] = int(cells[fj_idx].get_text().strip())
                
                logger.info(f"Extraídos totais para {student_name} na tabela {pfj_tables.index(table_info)+1}: P={result['P']}, F={result['F']}, FJ={result['FJ']}")
                
                # Se encontramos valores válidos, paramos a busca
                if result['P'] > 0 or result['F'] > 0 or result['FJ'] > 0:
                    return result
        
        # PASSO 3: Se não encontrou em nenhuma tabela, tentar outros métodos
        # Busca por todas as ocorrências do nome do aluno e números próximos
        student_spans = []
        for span in soup.find_all('span'):
            if span.string and isinstance(span.string, str) and student_name in span.string:
                student_spans.append(span)
        
        for span in student_spans:
            # Encontra a célula e linha do aluno
            td = span.find_parent('td')
            if not td:
                continue
                
            tr = td.find_parent('tr')
            if not tr:
                continue
            
            # Extrai todos os números desta linha
            numbers = []
            for cell in tr.find_all('td'):
                cell_text = cell.get_text().strip()
                if cell_text.isdigit() and len(cell_text) < 4:  # Evita números muito grandes (ex: anos)
                    numbers.append(int(cell_text))
            
            # Se encontrou pelo menos 3 números, assume que podem ser P, F, FJ
            if len(numbers) >= 3:
                # Pega os três últimos números na sequência exata em que aparecem
                last_three = numbers[-3:]
                if len(last_three) == 3:
                    # Pega os últimos números encontrados, preservando a ordem em que aparecem
                    result['P'] = last_three[0]
                    result['F'] = last_three[1]
                    result['FJ'] = last_three[2]
                    
                    logger.info(f"Extraídos totais preservando a ordem para {student_name}: P={result['P']}, F={result['F']}, FJ={result['FJ']}")
                    return result
    
    except Exception as e:
        logger.error(f"Erro ao extrair totais para {student_name}: {str(e)}")
    
    # Se chegou aqui, não conseguiu extrair os totais
    if result['P'] == 0 and result['F'] == 0 and result['FJ'] == 0:
        logger.warning(f"Não foi possível extrair totais para {student_name}, retornando valores padrão")
    
    return result


def analyze_elementary_file(html_content, filename=None):
    """
    Analisa um arquivo HTML de ensino fundamental ou infantil.
    Implementação unificada que integra os algoritmos de análise.
    
    No ensino fundamental, cada dia tem múltiplas chamadas (uma para cada matéria),
    então a contagem de faltas por mês é tratada de forma diferenciada para
    não ser artificialmente inflada.
    
    Args:
        html_content (str): Conteúdo HTML completo
        filename (str, optional): Nome do arquivo de origem, usado para extrair informação da turma
    
    Returns:
        dict: Resultado da análise no formato padronizado
    """
    try:
        # 1. Extrai informações básicas, passando o nome do arquivo
        info = get_school_info(html_content, filename)
        
        # 2. Extrai a lista de alunos
        students = get_student_list(html_content)
        
        # 3. Determina o tipo de educação (agora retorna um dicionário com nível e obrigatoriedade)
        education_info = determine_education_type(info['class_name'])
        
        # 4. Prepara o resultado final no formato esperado
        result = {
            'class_name': info['class_name'],
            'school_name': info['unit_name'],
            'education_type': education_info['nivel'],  # Mantém compatibilidade com código antigo
            'is_compulsory': education_info['obrigatorio'],  # Novo campo para obrigatoriedade
            'students': []
        }
        
        # 5. Processa cada aluno
        for student_name in students:
            # 5.1. Extrai totais do aluno
            totals = find_totals_in_html(html_content, student_name)
            
            # 5.2. Processa as faltas por mês (para TODOS os tipos de educação)
            # Removendo a restrição anterior que aplicava somente para "infantil"
            attendance = process_student_attendance(html_content, student_name)
            
            # 5.3. Cria o dicionário de dados do aluno mantendo zeros nas colunas principais
            student_data = {
                'aluno': student_name,  # Campo 'aluno' é usado pelo rules_engine
                'name': student_name,   # Campo 'name' usado em alguns lugares
                'P': totals.get('P', 0),  # Mantém zero quando não há presença
                'F': totals.get('F', 0),  # Mantém zero quando não há faltas
                'FJ': totals.get('FJ', 0),  # Mantém zero quando não há faltas justificadas
                'unidade': info['unit_name'],
                'escola': info['unit_name'],  # Manter compatibilidade
                'turma': info['class_name'],
                'dias_letivos': info.get('school_days', 0),
                'education_type': education_info['nivel'],  # Tipo de educação (infantil ou fundamental)
                'is_compulsory': education_info['obrigatorio']  # Se é obrigatório (True/False)
            }
            
            # Aplica faltas_por_mes para TODOS os tipos de educação
            # Mas com tratamento especial para ensino fundamental
            student_data['faltas_por_mes'] = attendance.get('faltas_por_mes', {})
            student_data['maior_falta_mensal'] = attendance.get('maior_falta_mensal', 0)
            student_data['faltas_por_mes_texto'] = attendance.get('faltas_por_mes_texto', '')
            
            # Tratamento especial para fundamental: substituir faltas_por_mes com "N/A"
            if education_info['nivel'] == 'fundamental':
                # Substitui os dados de faltas por mês com "N/A" para ensino fundamental
                student_data['faltas_por_mes'] = {}
                student_data['maior_falta_mensal'] = 0
                student_data['faltas_por_mes_texto'] = "N/A"
                student_data['faltas_por_mes_txt'] = "Não aplicável para Ensino Fundamental"
            
            # 5.4. Calcula as estatísticas sempre usando os valores numéricos
            # Garantimos que esses valores são sempre números na seção 5.3
            total_aulas = student_data['P'] + student_data['F'] + student_data['FJ']
            if total_aulas > 0:
                student_data['percentual_presenca'] = round((student_data['P'] / total_aulas) * 100, 1)
            else:
                student_data['percentual_presenca'] = 0
                
            # 5.5. Adiciona porcentagem de faltas justificadas usando valores numéricos
            total_faltas = student_data['F'] + student_data['FJ']
            if total_faltas > 0:
                student_data['percentual_justificado'] = round((student_data['FJ'] / total_faltas) * 100, 1)
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


def analyze_attendance_html(html_content, filename=None):
    """
    Função principal para analisar os dados de frequência de um arquivo HTML.
    Esta é a função de entrada principal do módulo, que deve ser chamada por aplicações externas.
    
    Args:
        html_content (str): Conteúdo HTML completo
        filename (str, optional): Nome do arquivo sendo processado, usado para extrair nome da turma
        
    Returns:
        dict: Dados processados com todas as informações relevantes
    """
    logger.info(f"Iniciando análise de arquivo HTML {filename or ''}")
    
    # Usa o método unificado de análise, passando o nome do arquivo para identificar a turma
    result = analyze_elementary_file(html_content, filename)
    
    logger.info(f"Análise concluída. {len(result.get('students', []))} alunos processados.")
    return result


def get_month_name(month_number):
    """
    Converte número do mês para nome abreviado em português.
    
    Args:
        month_number (int): Número do mês (1-12)
        
    Returns:
        str: Nome abreviado do mês em português
    """
    month_names = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
        5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
        9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }
    return month_names.get(month_number, str(month_number))