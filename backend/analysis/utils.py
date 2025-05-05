import logging
import datetime
import os

def get_month_name(month_number):
    """
    Convert month number to Portuguese month name abbreviation.
    
    Args:
        month_number (int): Month number (1-12)
        
    Returns:
        str: Portuguese month name abbreviation
    """
    month_names = {
        1: 'Jan',
        2: 'Fev',
        3: 'Mar',
        4: 'Abr',
        5: 'Mai',
        6: 'Jun',
        7: 'Jul',
        8: 'Ago',
        9: 'Set',
        10: 'Out',
        11: 'Nov',
        12: 'Dez'
    }
    
    return month_names.get(month_number, str(month_number))


class CustomLogFormatter(logging.Formatter):
    """
    Formatador personalizado de logs conforme o padrão específico do projeto.
    Formato: YYYY-MM-DD HH:MM:SS [LEVEL] [módulo        ] função             - chave=valor, chave="valor com espaços"
    """
    def __init__(self):
        super().__init__()

    def format(self, record):
        # Padronização dos módulos para 15 caracteres
        module_name = record.name.replace('html_parser.', '').replace('rules_engine.', '').ljust(15)
        level_name = record.levelname.ljust(5)[:5]
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Extrai o nome da função do nome do módulo se possível
        func_name = record.funcName.ljust(20)[:20]
        
        # Formatar a mensagem principal para separar os parâmetros
        msg = record.getMessage()
        
        # Se não contiver parâmetros após um traço, adicionar um
        if ' - ' not in msg and ' – ' not in msg:
            formatted_msg = f"{msg} – "
        else:
            formatted_msg = msg
        
        return f"{timestamp} [{level_name}] [{module_name}] {func_name} – {formatted_msg}"


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
    """Gera um ID de lote com base na data e hora atual"""
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
