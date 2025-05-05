#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PAESTRO - Módulo de Análise de Chamadas Escolares

Este pacote contém as funcionalidades de análise e processamento de chamadas escolares,
com foco na análise de faltas por mês, classificação de alunos e extração de dados
de arquivos HTML de chamada.

Componentes principais:
- analise_parser.py: Algoritmo especializado para arquivos HTML de ensino fundamental
- direct_parser.py: Implementação principal do parser de frequência para todos os tipos de ensino
- rules_engine.py: Regras de classificação para alunos (faltosos, monitoração, etc.)
- utils.py: Utilitários compartilhados como log formatado e conversão de meses

Originalmente desenvolvido como módulo independente 'analise_chamadas',
agora consolidado diretamente na estrutura principal do PAESTRO.
"""

__version__ = '2.0.0'
__author__ = 'Secretaria de Educação'
__copyright__ = 'Copyright 2025, Secretaria de Educação'

from .analise_parser import analyze_attendance_html
from .rules_engine import apply_classification_rules
from .utils import setup_new_logger, get_month_name, get_batch_id