#!/usr/bin/env python3
"""Maqueta el Markdown aprobado sin cambiar su contenido comercial.

Uso (desde cualquier directorio):
  uv run --with reportlab --with pymupdf /ruta/a/generar_pdf.py

Solo escribe el PDF junto a este script; las imágenes de QA quedan en /tmp.
Fuentes: Arial local de macOS o DejaVu Sans local de Linux.
"""
from collections import Counter
from html import escape
from pathlib import Path
import re
import tempfile
import unicodedata

import pymupdf as fitz
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'propuesta-economica.md'
OUTPUT = HERE / 'propuesta-economica-cisne-negro.pdf'
PAGE_W, PAGE_H = A4
MARGIN = 46
CONTENT_W = PAGE_W - 2 * MARGIN
INK = colors.HexColor('#171512')
MUTED = colors.HexColor('#6e6558')
PAPER = colors.HexColor('#fcfaf5')
AMBER = colors.HexColor('#d1a457')
WASH = colors.HexColor('#f1e5ce')
LINE = colors.HexColor('#e0d8cb')


def register_fonts():
    alternatives = [
        (Path('/System/Library/Fonts/Supplemental'),
         ('Arial.ttf', 'Arial Bold.ttf', 'Arial Italic.ttf', 'Arial Bold Italic.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu'),
         ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans-Oblique.ttf', 'DejaVuSans-BoldOblique.ttf')),
    ]
    for folder, names in alternatives:
        if all((folder / name).is_file() for name in names):
            for role, filename in zip(('CN', 'CN-Bold', 'CN-Italic', 'CN-BoldItalic'), names):
                pdfmetrics.registerFont(TTFont(role, str(folder / filename)))
            pdfmetrics.registerFontFamily('CN', normal='CN', bold='CN-Bold',
                                         italic='CN-Italic', boldItalic='CN-BoldItalic')
            return
    raise RuntimeError('Se requieren Arial de macOS o DejaVu Sans de Linux para incrustar las fuentes.')


register_fonts()
BODY = ParagraphStyle('Body', fontName='CN', fontSize=10.4, leading=15.25,
                      textColor=INK, spaceAfter=10, allowWidows=0, allowOrphans=0)
SMALL = ParagraphStyle('Small', parent=BODY, fontSize=9.2, leading=13.2, textColor=MUTED, spaceAfter=6)
TITLE = ParagraphStyle('Title', parent=BODY, fontName='CN-Bold', fontSize=25, leading=29,
                       spaceAfter=13)
SUBTITLE = ParagraphStyle('Subtitle', parent=BODY, fontName='CN-Bold', fontSize=12.2,
                          leading=17, spaceAfter=9)
H2 = ParagraphStyle('H2', parent=BODY, fontName='CN-Bold', fontSize=18.7, leading=23,
                    spaceBefore=0, spaceAfter=18, keepWithNext=True)
H3 = ParagraphStyle('H3', parent=BODY, fontName='CN-Bold', fontSize=12.2, leading=17,
                    spaceBefore=13, spaceAfter=7, keepWithNext=True)
CELL = ParagraphStyle('Cell', parent=BODY, fontSize=9.6, leading=13.7, spaceAfter=0)
CELL_R = ParagraphStyle('CellR', parent=CELL, alignment=TA_RIGHT)
CELL_HEAD = ParagraphStyle('CellHead', parent=CELL, fontName='CN-Bold', textColor=colors.white)
CELL_HEAD_R = ParagraphStyle('CellHeadR', parent=CELL_HEAD, alignment=TA_RIGHT)
BULLET = ParagraphStyle('Bullet', parent=BODY, leftIndent=12, firstLineIndent=0,
                        bulletIndent=0, spaceAfter=9, fontSize=10.0, leading=14.4)
CALLOUT = ParagraphStyle('Callout', parent=BODY, fontSize=11.3, leading=16.5, spaceAfter=0)


def inline(text):
    text = escape(text.strip())
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)


def para(text, style=BODY):
    return Paragraph(inline(text), style)


def callout(text):
    t = Table([[para(text, CALLOUT)]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), WASH),
        ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 13), ('BOTTOMPADDING', (0, 0), (-1, -1), 13),
    ]))
    return KeepTogether([t, Spacer(1, 13)])


def markdown_table(lines):
    rows = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines]
    alignment = [item.endswith(':') for item in rows[1]]
    rows = [rows[0], *rows[2:]]
    if len(rows[0]) == 3:
        widths = [CONTENT_W * .12, CONTENT_W * .66, CONTENT_W * .22]
    elif rows[0][-1] == 'Importe MXN':
        widths = [CONTENT_W * .76, CONTENT_W * .24]
    else:
        widths = [CONTENT_W * .29, CONTENT_W * .71]
    data = []
    for row_index, row in enumerate(rows):
        cell_row = []
        for col, text in enumerate(row):
            style = (CELL_HEAD_R if alignment[col] else CELL_HEAD) if row_index == 0 else (CELL_R if alignment[col] else CELL)
            cell_row.append(para(text, style))
        data.append(cell_row)
    table = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT', splitByRow=1)
    commands = [
        ('BACKGROUND', (0, 0), (-1, 0), INK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, 0), 10), ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 1), (-1, -1), 9),
        ('LINEBELOW', (0, 1), (-1, -1), .4, LINE),
    ]
    for idx in range(1, len(rows)):
        commands.append(('BACKGROUND', (0, idx), (-1, idx), colors.white if idx % 2 else colors.HexColor('#f6f2ea')))
    if 'Total de implementación' in rows[-1][0]:
        commands.append(('BACKGROUND', (0, len(rows)-1), (-1, len(rows)-1), WASH))
    table.setStyle(TableStyle(commands))
    return KeepTogether([table, Spacer(1, 13)])


def blocks(markdown):
    result = []
    lines = markdown.strip().splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith('|'):
            table = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                table.append(lines[index])
                index += 1
            result.append(markdown_table(table))
            continue
        if line.startswith('### '):
            result.append(para(line[4:], H3))
            index += 1
            continue
        if line.startswith('## '):
            result.append(para(line[3:], H2))
            index += 1
            continue
        if line.startswith('- '):
            result.append(KeepTogether([Paragraph(inline(line[2:]), BULLET, bulletText='•')]))
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].lstrip().startswith(('|', '#', '- ')):
            paragraph.append(lines[index].strip())
            index += 1
        text = ' '.join(paragraph)
        if text.startswith('**Para iniciar:'):
            result.append(callout(text))
        else:
            result.append(para(text))
    return result


class NumberedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        kwargs['invariant'] = 1
        super().__init__(*args, **kwargs)
        self._states = []

    def showPage(self):
        self._states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        count = len(self._states)
        for state in self._states:
            self.__dict__.update(state)
            self.setFillColor(MUTED)
            self.setFont('CN', 8)
            self.drawString(MARGIN, 29, 'CN-2026-01  ·  7 de octubre de 2026')
            self.drawRightString(PAGE_W-MARGIN, 29, f'{self._pageNumber} / {count}')
            super().showPage()
        super().save()


def decoration(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(INK)
    canvas.setFont('CN-Bold', 8)
    canvas.drawString(MARGIN, PAGE_H-30, 'SOFTVIBES')
    canvas.setFillColor(MUTED)
    canvas.setFont('CN', 8)
    canvas.drawRightString(PAGE_W-MARGIN, PAGE_H-30, 'CERVECERÍA CISNE NEGRO')
    canvas.setFillColor(AMBER)
    canvas.rect(MARGIN, PAGE_H-43, 25, 2, fill=1, stroke=0)
    canvas.restoreState()


def make_story(source):
    sections = re.split(r'(?m)^(?=## \d+\. )', source)
    assert len(sections) == 8, 'El documento debe contener las siete secciones aprobadas.'
    opening = sections[0].strip().split('\n\n')
    assert len(opening) == 5
    title = opening[0].removeprefix('# ')
    metadata = opening[1].splitlines()
    story = [para(title, TITLE), para(metadata[0], SUBTITLE)]
    story.extend(para(line, SMALL) for line in metadata[1:])
    story.extend([Spacer(1, 9), para(opening[2]), callout(opening[3]), para(opening[4]), Spacer(1, 5)])
    story.extend(blocks(sections[1]))
    story.append(PageBreak())
    deliveries = sections[2].split('### CMS editorial', 1)
    assert len(deliveries) == 2
    story.extend(blocks(deliveries[0]))
    story.append(PageBreak())
    story.append(para('2. Qué se entrega', H2))
    story.append(para('CMS y entrega final', SMALL))
    story.extend(blocks('### CMS editorial' + deliveries[1]))
    story.append(PageBreak())
    story.extend(blocks(sections[3]))
    story.append(PageBreak())
    story.extend(blocks(sections[4]))
    story.append(PageBreak())
    story.extend(blocks(sections[7]))
    story.append(PageBreak())
    story.extend(blocks(sections[5]))
    story.append(Spacer(1, 5))
    story.extend(blocks(sections[6]))
    return story


def main():
    source = SOURCE.read_text(encoding='utf-8')
    frame = Frame(MARGIN, 53, CONTENT_W, PAGE_H-117, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, pageTemplates=[PageTemplate(id='Proposal', frames=frame, onPage=decoration)],
                          title='Propuesta económica para Cervecería Cisne Negro', author='Softvibes',
                          subject='Página web, menú digital, Pasaporte Cisne y CMS',
                          allowSplitting=1)
    doc.build(make_story(source), canvasmaker=NumberedCanvas)
    pdf = fitz.open(OUTPUT)
    assert len(pdf) == 8, f'Se esperaban 8 páginas; se obtuvieron {len(pdf)}. Revisar distribución.'
    content = '\n'.join(page.get_text() for page in pdf)
    expected_amounts = Counter(re.findall(r'\$[\d,]+', source))
    actual_amounts = Counter(re.findall(r'\$[\d,]+', content))
    assert expected_amounts == actual_amounts, (expected_amounts, actual_amounts)
    assert '\ufffd' not in content and '\x00' not in content, 'Glifos inválidos en el PDF.'
    # Verifica cada bloque original, incluidos celdas y acentos, en el texto extraído.
    def normalize(text):
        return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()
    extracted = normalize(content)
    for raw in source.splitlines():
        if not raw.strip() or re.fullmatch(r'[|\-: ]+', raw):
            continue
        pieces = raw.strip().strip('|').split('|') if raw.startswith('|') else [re.sub(r'^#{1,3} |^- ', '', raw)]
        for piece in pieces:
            text = normalize(piece.replace('**', ''))
            assert text in extracted, f'Contenido ausente o alterado: {text[:100]}'
    qa = Path(tempfile.mkdtemp(prefix='cisne-negro-propuesta-qa-', dir='/tmp'))
    for n, page in enumerate(pdf, 1):
        for word in page.get_text('words'):
            x0, y0, x1, y1 = word[:4]
            assert 20 <= x0 < x1 <= PAGE_W-20 and 15 <= y0 < y1 <= PAGE_H-15, (n, word)
        page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False).save(qa / f'pagina-{n:02d}.png')
    print(f'PDF: {OUTPUT}')
    print(f'QA: {qa}')
    print(f'OK: {len(pdf)} páginas; importes idénticos; contenido completo; acentos preservados; texto dentro de márgenes.')


if __name__ == '__main__':
    main()
