"""
PAESTRO - Módulo de Análise de Chamadas Escolares

Este pacote contém as funcionalidades de análise e processamento de chamadas escolares,
com foco na análise de faltas por mês, classificação de alunos e extração de dados
de arquivos HTML de chamada.

Componentes principais:
- analise_parser.py: Algoritmo unificado para análise de arquivos HTML de todos os tipos de ensino
- rules_engine.py: Regras de classificação para alunos (faltosos, monitoração, etc.)
- utils.py: Utilitários compartilhados como log formatado e conversão de meses

Organização atualizada em Maio 2025 para unificar o código previamente dividido
em múltiplos arquivos.
"""

__version__ = '3.0.0'
__author__ = 'Secretaria de Educação'
__copyright__ = 'Copyright 2025, Secretaria de Educação'

from .analise_parser import analyze_attendance_html, find_totals_in_html, get_school_info, get_student_list
from .rules_engine import apply_classification_rules
from .utils import setup_new_logger, get_month_name, get_batch_id, MONTH_NAMES