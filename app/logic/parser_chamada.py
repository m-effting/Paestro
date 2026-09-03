from lxml import html
import re
import os
import logging

logger = logging.getLogger(__name__)

def parse_chamada(html_content, filename=None):
    """
    Extrai turmas, alunos e unidade de:
    - Relatórios de Chamada
    - Relatórios de Estudantes Matriculados

    Retorna:
    {
        "schools": {
            "UNIDADE": {
                "TURMA": [
                    "ALUNO 1",
                    "ALUNO 2"
                ]
            }
        }
    }
    """

    # Permite receber caminho de arquivo
    if isinstance(html_content, str) and os.path.exists(html_content):

        if not filename:
            filename = os.path.basename(html_content)

        try:
            with open(html_content, "r", encoding="utf-8") as f:
                html_content = f.read()

        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return {"schools": {}}

    if not html_content:
        return {"schools": {}}

    try:
        tree = html.fromstring(html_content)

    except Exception as e:
        logger.error(f"Erro ao processar HTML: {e}")
        return {"schools": {}}

    page_text = tree.text_content()

    # =====================================================
    # RELATÓRIO DE ESTUDANTES MATRICULADOS
    # =====================================================

    if "RELATÓRIO DE ESTUDANTES MATRICULADOS" in page_text:

        schools = {}

        pages = tree.xpath("//table[contains(@class,'jrPage')]")

        # fallback caso não encontre jrPage
        if not pages:
            pages = [tree]

        for page in pages:

            page_text = page.text_content()

            current_turma = None
            current_unidade = None

            # CORREÇÃO: na exportação HTML deste relatório, o parêntese de
            # FECHAMENTO de "Turma: 1º ANO - 1 (UNIDADE ...)" costuma ficar
            # em um elemento separado e não aparece no texto da página. Por
            # isso não podemos exigir "(...)" completo — basta capturar o
            # que vem depois de "Turma:" até o "(" de abertura, que já traz
            # o nome completo da turma (ex.: "1º ANO - 1", "1º ANO - 3").
            turma_match = re.search(
                r"Turma:\s*([^(\n]+)\(",
                page_text,
                re.IGNORECASE
            )

            # Tenta também capturar a unidade, caso o parêntese feche
            # normalmente nesta página (funciona p/ 6º ao 8º ano, por ex.)
            turma_unidade_match = re.search(
                r"Turma:\s*([^(]+)\(([^)]+)\)",
                page_text,
                re.IGNORECASE
            )

            if turma_unidade_match:
                current_turma = turma_unidade_match.group(1).strip()
                current_unidade = turma_unidade_match.group(2).strip()
            elif turma_match:
                current_turma = turma_match.group(1).strip()
                # unidade será resolvida pelo fallback via cells[4] abaixo

            rows = page.xpath(".//tr")

            for row in rows:

                cells = [
                    re.sub(r"\s+", " ", td.text_content()).strip()
                    for td in row.xpath("./td")
                ]

                cells = [c for c in cells if c]

                # ignora cabeçalhos
                if len(cells) < 8:
                    continue

                # primeira coluna precisa ser código
                if not re.fullmatch(r"\d+", cells[0]):
                    continue

                nome = cells[1]

                unidade = current_unidade
                turma = current_turma

                # fallback
                if not unidade and len(cells) > 4:
                    unidade = cells[4]

                if not turma and len(cells) > 5:
                    turma = cells[5]

                if not unidade:
                    unidade = "Unidade não identificada"

                if not turma:
                    turma = "Turma não identificada"

                schools.setdefault(unidade, {})
                schools[unidade].setdefault(turma, [])
                schools[unidade][turma].append(nome)

        return {"schools": schools}

    # =====================================================
    # RELATÓRIO DE CHAMADA ORIGINAL
    # =====================================================

    classes = {}
    current_turma = None
    unidade_name = None

    TURMA_REGEX = re.compile(
        r'Turma:\s*((\d+\s*[\u00ba\u00aa]*\s*ANO\s*-\s*\d+)|([^(\n]+))\s*(?:\(([^)\n]+)\)|$)',
        re.UNICODE
    )

    possible_name_locations = [
        tree.xpath("//title/text()"),
        tree.xpath("//h1/text()"),
        tree.xpath("//h2/text()"),
        tree.xpath("//div[contains(@class,'header')]//text()"),
        tree.xpath("//span[contains(@class,'school-name')]//text()")
    ]

    for location in possible_name_locations:

        if location and not unidade_name:

            text = " ".join(
                t.strip()
                for t in location
                if t.strip()
            )

            if (
                text
                and "Turma:" not in text
                and "Total" not in text
            ):
                unidade_name = text.strip()
                break

    tables = tree.xpath("//table[contains(@class,'jrPage')]")

    for table in tables:

        rows = table.xpath(".//tr")

        turma_row = None

        for row in rows:

            row_text = " ".join(row.itertext()).strip()

            if (
                "Turma:" in row_text
                and "Total de Matrículas" not in row_text
            ):
                turma_row = row
                break

        if turma_row is not None:

            turma_text = " ".join(
                turma_row.itertext()
            ).strip()

            match = TURMA_REGEX.search(turma_text)

            if match:

                current_turma = match.group(1).strip()

                if current_turma not in classes:
                    classes[current_turma] = []

        if not current_turma:
            continue

        header_row = None
        header_index = None

        for idx, row in enumerate(rows):

            text = row.text_content().strip()

            if "Código" in text and "Nome" in text:

                header_row = row
                header_index = idx
                break

        if header_row is None:
            continue

        header_cells = (
            header_row.xpath(".//th")
            or header_row.xpath(".//td")
        )

        nome_index = next(
            (
                i for i, c in enumerate(header_cells)
                if "Nome" in c.text_content()
            ),
            None
        )

        if nome_index is None:
            continue

        for row in rows[header_index + 1:]:

            row_text = row.text_content().strip()

            if (
                "Total de Matrículas" in row_text
                or "Turma:" in row_text
            ):
                break

            cells = row.xpath(".//td")

            if len(cells) > nome_index:

                aluno = (
                    cells[nome_index]
                    .text_content()
                    .strip()
                )

                if aluno and len(aluno) > 1:
                    classes[current_turma].append(aluno)

    if not unidade_name and filename:

        unidade_name = os.path.splitext(filename)[0]

    unidade_name = unidade_name or "Unidade não identificada"

    return {
        "schools": {
            unidade_name: classes
        }
    }

