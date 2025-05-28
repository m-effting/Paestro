import logging
import datetime
import os

"""
PAESTRO - Módulo de Análise de Chamadas Escolares - Utilitários

Este módulo contém funções e classes utilitárias compartilhadas por todos os 
componentes do módulo de análise de chamadas escolares.

Funções principais:
- get_month_name: Converte número do mês para nome em português
- setup_new_logger: Configura um logger personalizado
- get_batch_id: Gera um ID único para lotes de processamento

Classes:
- CustomLogFormatter: Formatador personalizado para logs

Autor: Equipe PAESTRO
Data: Maio 2025
"""

# Mapeamento de mês número -> nome (para output das faltas por mês)
MONTH_NAMES = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

def get_month_name(month_number):
    """
    Converte número do mês para nome abreviado em português.
    
    Args:
        month_number (int): Número do mês (1-12)
        
    Returns:
        str: Nome abreviado do mês em português
    """
    try:
        # Garantir que month_number seja um inteiro válido entre 1-12
        month_int = int(month_number)
        if 1 <= month_int <= 12:
            return MONTH_NAMES.get(month_int)
    except (ValueError, TypeError):
        pass
        
    # Se não for possível converter ou estiver fora do intervalo, retorna o valor recebido
    return str(month_number)


class CustomLogFormatter(logging.Formatter):
    """
    Formatador personalizado de logs conforme o padrão específico do projeto.
    Formato: YYYY-MM-DD HH:MM:SS [LEVEL] [módulo] - mensagem
    """
    def __init__(self):
        super().__init__()

    def format(self, record):
        # Versão mais concisa do formatador de logs
        module_name = record.name.replace('html_parser.', '').replace('rules_engine.', '')
        level_name = record.levelname.ljust(5)[:5]
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Formatar a mensagem principal de forma mais concisa
        msg = record.getMessage()
        
        # Remove detalhes técnicos excessivos para mensagens de DEBUG
        if record.levelno == logging.DEBUG:
            # Trunca mensagens muito longas
            if len(msg) > 100:
                msg = msg[:97] + "..."
        
        return f"{timestamp} [{level_name}] [{module_name}] - {msg}"


def setup_new_logger(log_filename='attendance_parser.log'):
    """
    Configura um logger personalizado para o sistema.
    
    Args:
        log_filename: Nome do arquivo de log
        
    Returns:
        Logger configurado
    """
    # Remover handlers anteriores
    for handler in logging.root.handlers[:]: 
        logging.root.removeHandler(handler)
    
    # Configurar o logger raiz
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Handler para arquivo
    file_handler = logging.FileHandler(log_filename, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CustomLogFormatter())
    logger.addHandler(file_handler)
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomLogFormatter())
    logger.addHandler(console_handler)
    
    return logger


def get_batch_id():
    """
    Gera um ID de lote baseado na data e hora atual.
    
    Formato: YYYYMMDD_HHMMSS (ano, mês, dia, hora, minuto, segundo)
    
    Returns:
        str: ID único de lote para o processamento atual
    """
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
