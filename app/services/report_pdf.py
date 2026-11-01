"""Private report export with explicit wrapping and pagination, no interpreted markup."""
from io import BytesIO
from pathlib import Path
import reportlab
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = 'DocuMindVera'
BOLD = 'DocuMindVeraBold'
WIDTH, HEIGHT = 595.44, 841.68
MARGIN = 48
BOTTOM = 50


def render(report):
    for name, filename in ((FONT, 'Vera.ttf'), (BOLD, 'VeraBd.ttf')):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(Path(reportlab.__file__).parent / 'fonts' / filename)))
    glyphs = pdfmetrics.getFont(FONT).face.charToGlyph
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(WIDTH, HEIGHT))
    pdf.setTitle(report['title'])
    pdf.setAuthor('DocuMind')
    y = HEIGHT - MARGIN

    def safe(value):
        return ''.join(c if ord(c) in glyphs or c in '\n\t' else f'[U+{ord(c):04X}]' for c in str(value))

    def lines(value, size=9, font=FONT, indent=0):
        available = WIDTH - 2 * MARGIN - indent * 2
        result = []
        for paragraph in safe(value).split('\n'):
            current = ''
            for word in paragraph.split():
                candidate = (current + ' ' + word).strip()
                if pdfmetrics.stringWidth(candidate, font, size) <= available:
                    current = candidate
                    continue
                if current:
                    result.append(current)
                    current = ''
                # Hashes, filenames and long unbroken literals must also wrap.
                for character in word:
                    if current and pdfmetrics.stringWidth(current + character, font, size) > available:
                        result.append(current)
                        current = ''
                    current += character
            result.append(current)
        return result

    def footer():
        pdf.setFont(FONT, 7)
        pdf.setFillColor(colors.HexColor('#526573'))
        pdf.drawString(MARGIN, 27, 'DocuMind | Private workspace report | Human review required')
        pdf.drawRightString(WIDTH - MARGIN, 27, f'Page {pdf.getPageNumber()}')

    def new_page():
        nonlocal y
        footer()
        pdf.showPage()
        y = HEIGHT - MARGIN

    def ensure(height):
        if y - height < BOTTOM:
            new_page()

    def height(value, size=9, bold=False, indent=0):
        return len(lines(value, size, BOLD if bold else FONT, indent)) * (size * 1.5) + 8

    def paragraph(value, size=9, bold=False, muted=False, quote=False):
        nonlocal y
        font = BOLD if bold else FONT
        indent = 8 if quote else 0
        leading = size * 1.5
        for line in lines(value, size, font, indent):
            ensure(leading + 2)
            if quote:
                pdf.setFillColor(colors.HexColor('#f1f5f7'))
                pdf.rect(MARGIN, y - leading + 2, WIDTH - 2 * MARGIN, leading, fill=1, stroke=0)
            pdf.setFont(font, size)
            pdf.setFillColor(colors.HexColor('#526573' if muted else '#172b3a'))
            pdf.drawString(MARGIN + indent, y - size, line)
            y -= leading
        y -= 8

    def heading(value, major=False):
        size = 15 if major else 12
        ensure(height(value, size, True) + 24)
        paragraph(value, size, bold=True)

    snapshot = report['snapshot']
    paragraph('DOCUMIND / EVIDENCE REVIEW', 8, muted=True)
    paragraph(report['title'], 22, bold=True)
    heading('Reviewed comparison report')
    paragraph('Saved: ' + report['created_at'] + '\nReport: ' + report['id'] + '\nMethod: ' + snapshot['method'], 8, muted=True)
    heading('STALE SOURCE REVISION - re-review required' if report['stale'] else 'Source revisions match at export time.')
    paragraph('Findings reflect a bounded evidence sample. They do not establish legal equivalence or whole-document completeness.')
    heading('Summary', True)
    for label, count in snapshot['summary'].items():
        paragraph(f'{label.replace("_", " ").title()}: {count}')
    heading('Scope and limitations', True)
    limitations = list(snapshot['limitations'])
    limitations += [f"{item['file_id']}: {item['reason']}" for item in snapshot.get('extraction_limitations', [])]
    if snapshot.get('extraction_truncated'):
        limitations.append('Fact limit reached; only a partial sample is included.')
    limitations += ['Unsupported font characters are displayed as [U+XXXX]; JSON export preserves exact Unicode.', report['retention']]
    for limitation in limitations:
        paragraph(limitation)
    sources = {source['evidence_id']: source for source in snapshot['sources']}
    new_page()
    heading('Evidence-linked findings', True)
    for index, finding in enumerate(snapshot['findings'], 1):
        topic = f"{index}. " + finding['topic'].replace('\u2192', '->')
        label = finding['classification'].replace('_', ' ').title()
        ensure(height(topic, 12, True) + height(label, 8) + height(finding['explanation']))
        heading(topic)
        paragraph(label, 8, muted=True)
        paragraph(finding['explanation'])
        for document in finding['documents']:
            if not document['facts']:
                ensure(height(document['filename'], 11, True) + 25)
                paragraph(document['filename'], 11, bold=True)
                paragraph('Not observed in the bounded evidence sample.')
            for fact in document['facts']:
                source = sources.get(fact['evidence_id'])
                values = ', '.join(fact['values'])
                metadata = ''
                if source:
                    metadata = (f"Source {source['evidence_id']} | {source['filename']} | page {source['page_number']}\n"
                                f"File {source['file_id']} | chunk {source['source_id']}\n"
                                f"Published run {source['processing_run_id']}\nContent SHA-256 {source['content_sha256']}")
                block_height = height(document['filename'], 11, True) + height(values)
                if source:
                    block_height += height(source['excerpt'], indent=8) + height(metadata, 8)
                # Normal application quotations are <=1000 chars. Very long
                # defensive inputs still paginate line by line, never clip.
                if block_height <= HEIGHT - MARGIN - BOTTOM:
                    ensure(block_height)
                paragraph(document['filename'], 11, bold=True)
                paragraph(values)
                if source:
                    paragraph(source['excerpt'], quote=True)
                    ensure(height(metadata, 8))
                    paragraph(metadata, 8, muted=True)
    heading('Document revisions', True)
    for source in snapshot['documents']:
        state = next(state for state in report['source_states'] if state['file_id'] == source['file_id'])
        value = (f"{source['filename']} | {source['file_id']}\nSaved version: {source['document_version']}\n"
                 f"Current version: {state['current_version']}\nState: {'STALE' if state['stale'] else 'matches'}")
        ensure(height(value, 8))
        paragraph(value, 8, muted=True)
    footer()
    pdf.save()
    return output.getvalue()
