from lxml import html
import os
import re
import logging

logger = logging.getLogger(__name__)

def parse_chamada(html_content, filename=None):
    """Parse chamada HTML.

    `html_content` pode ser uma string com HTML ou um caminho para um arquivo HTML.
    Se for um caminho existente, o conteúdo será lido e `filename` ajustado.
    Retorna um dict com a chave `schools`.
    """

    # Se o usuário passou um caminho de arquivo em `html_content`, leia o arquivo
    if isinstance(html_content, str) and os.path.exists(html_content):
        if not filename:
            filename = os.path.basename(html_content)
        try:
            with open(html_content, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {html_content}: {e}")
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

        for row in tree.xpath("//tr"):

            cells = [
                td.text_content().strip()
                for td in row.xpath("./td")
            ]

            cells = [c for c in cells if c]


            if len(cells) < 9:
                continue

            if not re.fullmatch(r"\d+", cells[0]):
                continue

            codigo = cells[0]
            nome = cells[1]
            unidade = cells[4]
            turma = cells[5]

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

    tables = tree.xpath("//table[contains(@class,'jrPage')]")

    for table in tables:

        rows = table.xpath(".//tr")

        turma_row = None

        for row in rows:

            row_text = " ".join(row.itertext()).strip()

            if (
                "Turma:" in row_text and
                "Total de Matrículas" not in row_text
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
                "Total de Matrículas" in row_text or
                "Turma:" in row_text
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

    if not unidade_name:

        unidade_name = (
            os.path.splitext(filename)[0]
            if filename
            else "Unidade não identificada"
        )

    return {
        "schools": {
            unidade_name: classes
        }
    }