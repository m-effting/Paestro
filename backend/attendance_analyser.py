import os
import logging
import io
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename

# Import do módulo de análise de chamadas
from backend.analysis.direct_parser import analyze_attendance_html
from backend.analysis.rules_engine import apply_classification_rules
from backend.analysis.utils import setup_new_logger, get_batch_id

# Configure o logger
logger = setup_new_logger()

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    ALLOWED_EXTENSIONS = {'html', 'htm'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_file(df, file_format):
    """Gera um arquivo CSV ou Excel a partir de um DataFrame."""
    buffer = io.BytesIO()
    
    if file_format == 'csv':
        csv_data = df.to_csv(index=False, encoding='utf-8')
        buffer.write(csv_data.encode('utf-8'))
        buffer.seek(0)
        mime_type = 'text/csv'
    else:  # excel
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
            
            # Ajusta larguras das colunas
            worksheet = writer.sheets['Dados']
            for i, col in enumerate(df.columns):
                # Determina a largura ideal com base no conteúdo
                max_len = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)
        
        buffer.seek(0)
        mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return buffer, mime_type

def process_html_file(file_content, filename):
    """Processa um arquivo HTML e extrai os dados de frequência."""
    batch_id = get_batch_id()
    logger.info(f"Processando arquivo: {filename}", extra={"batch_id": batch_id})
    
    try:
        # Analisa o arquivo HTML usando o módulo analise_chamadas
        result = analyze_attendance_html(file_content)
        
        if not result or 'error' in result:
            error_message = result.get('error', 'Erro desconhecido ao analisar o arquivo') if result else 'Nenhum resultado retornado'
            logger.error(f"Erro no arquivo {filename}: {error_message}", extra={"batch_id": batch_id})
            return None, f"Erro no arquivo {filename}: {error_message}"
        
        logger.info(f"Arquivo {filename} processado com sucesso", extra={"batch_id": batch_id})
        return result, None
    
    except Exception as e:
        logger.error(f"Erro ao processar {filename}: {str(e)}", extra={"batch_id": batch_id})
        return None, f"Erro ao processar {filename}: {str(e)}"

def process_files(files):
    """Processa múltiplos arquivos HTML e combina os resultados."""
    batch_id = get_batch_id()
    logger.info(f"Iniciando processamento de lote: {batch_id}", extra={"batch_id": batch_id})
    
    all_results = []
    processed_files = []
    error_files = []
    
    for file in files:
        if file and allowed_file(file.filename):
            try:
                # Lê o conteúdo do arquivo
                file_content = file.read().decode('utf-8')
                
                # Processa o arquivo HTML
                result, error = process_html_file(file_content, file.filename)
                
                if result and not error:
                    school_data = result.get('school_data', {})
                    student_data = result.get('student_data', [])
                    
                    if student_data:
                        all_results.extend(student_data)
                        processed_files.append({
                            'name': file.filename,
                            'school': school_data.get('school_name', 'N/A'),
                            'class': school_data.get('class_name', 'N/A'),
                            'students': len(student_data)
                        })
                    else:
                        error_files.append({
                            'name': file.filename,
                            'error': 'Nenhum dado de aluno encontrado'
                        })
                else:
                    error_files.append({
                        'name': file.filename,
                        'error': error or 'Erro desconhecido'
                    })
                    
            except Exception as e:
                logger.error(f"Erro ao processar {file.filename}: {str(e)}", extra={"batch_id": batch_id})
                error_files.append({
                    'name': file.filename,
                    'error': str(e)
                })
        else:
            error_files.append({
                'name': getattr(file, 'filename', 'Unknown'),
                'error': 'Formato de arquivo não permitido'
            })
    
    # Aplica as regras de classificação
    classified_results = apply_classification_rules({'student_data': all_results})
    
    logger.info(f"Processamento concluído. {len(processed_files)} arquivos processados, {len(error_files)} com erro", 
              extra={"batch_id": batch_id})
    
    return {
        'data': classified_results,
        'processed_files': processed_files,
        'error_files': error_files
    }

def apply_classifications(results):
    """Aplica as regras de classificação de alunos."""
    return apply_classification_rules({'student_data': results})

def get_logs():
    """Obtém os logs recentes do analisador de frequência."""
    logs = []
    try:
        with open('attendance_parser.log', 'r', encoding='utf-8') as f:
            # Lê as últimas 100 linhas (ou menos se o arquivo for menor)
            lines = f.readlines()[-100:]
            logs = [line.strip() for line in lines]
    except Exception as e:
        logs = [f"Erro ao ler logs: {str(e)}"]
    
    return logs

def export_to_file(data, file_format):
    """Exporta os dados para um arquivo CSV ou Excel."""
    try:
        # Converte os dados para DataFrame
        df = pd.DataFrame(data)
        
        # Reordena e renomeia colunas
        columns_order = [
            'school_name', 'class_name', 'education_type', 'student_name', 
            'classification', 'status', 'attendance_percentage',
            'absence_total', 'justified_total', 'presence_total',
            'months_with_high_absence'
        ]
        
        # Filtra apenas colunas existentes no DataFrame
        available_columns = [col for col in columns_order if col in df.columns]
        df = df[available_columns]
        
        # Renomeia colunas para português
        column_names = {
            'school_name': 'Escola',
            'class_name': 'Turma',
            'education_type': 'Tipo de Ensino',
            'student_name': 'Aluno',
            'classification': 'Classificação',
            'status': 'Status',
            'attendance_percentage': 'Percentual de Presença (%)',
            'absence_total': 'Total de Faltas',
            'justified_total': 'Total de Faltas Justificadas',
            'presence_total': 'Total de Presenças',
            'months_with_high_absence': 'Meses com Excesso de Faltas'
        }
        
        df.rename(columns={col: column_names.get(col, col) for col in df.columns}, inplace=True)
        
        # Gera o arquivo no formato solicitado
        return generate_file(df, file_format)
    
    except Exception as e:
        logger.error(f"Erro ao exportar dados: {str(e)}")
        raise
