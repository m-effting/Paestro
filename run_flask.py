#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PAESTRO - Sistema de Gestão de Chamadas Escolares

Este é o script principal para iniciar o aplicativo PAESTRO,
que fornece ferramentas para importação, análise e exportação
de dados de chamadas escolares.
"""

import os
import sys

# Garantir que os módulos sejam encontrados corretamente
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Importar o app principal do PAESTRO
from backend.app import app


if __name__ == '__main__':
    # Iniciar o servidor na porta 5000, acessível por qualquer IP
    app.run(host='0.0.0.0', port=5000, debug=True)