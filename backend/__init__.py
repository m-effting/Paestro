#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PAESTRO - Backend do Sistema de Gestão de Chamadas Escolares

Este pacote contém o backend do sistema PAESTRO, com os módulos responsáveis
por importação, processamento, análise e exportação de dados de chamadas escolares.

Módulos principais:
- app.py: Aplicação Flask principal com rotas e lógica de visualização
- chamada_parser.py: Parser para extração de turmas e alunos na tela de importação
- analysis/: Subpacote com algoritmos avançados de análise de frequência
- excel_exporter.py: Exportação para Excel da lista de presença
- drive_exporter.py: Integração opcional com Google Drive
"""

__version__ = '1.0.0'
__author__ = 'Secretaria de Educação'
__copyright__ = 'Copyright 2025, Secretaria de Educação'