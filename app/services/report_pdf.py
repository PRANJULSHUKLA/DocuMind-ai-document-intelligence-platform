"""Paginated private report export; all user/document markup is escaped."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable

FONT_NAME = 'DocuMindVera'


def render(report):
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))
    glyphs = pdfmetrics.getFont(FONT_NAME).face.charToGlyph
    def safe(value):
        # Never silently drop unsupported glyphs. JSON retains original Unicode.
        text = ''.join(c if ord(c) in glyphs or c in '\n\t' else f'[U+{ord(c):04X}]' for c in str(value))
        return escape(text).replace('\n', '<br/>')
    styles = getSampleStyleSheet()
    for name in ('Title', 'Heading1', 'Heading2', 'BodyText'):
        styles[name].fontName = FONT_NAME
        styles[name].textColor = colors.HexColor('#172b3a')
    styles['Title'].fontSize = 23
    styles['Title'].leading = 29
    styles['BodyText'].fontSize = 9
    styles['BodyText'].leading = 14
    styles['BodyText'].spaceAfter = 8
    quote = ParagraphStyle('Evidence', parent=styles['BodyText'], backColor=colors.HexColor('#f1f5f7'), borderPadding=8, leftIndent=10, rightIndent=10, spaceBefore=6, spaceAfter=12)
    small = ParagraphStyle('Metadata', parent=styles['BodyText'], fontSize=8, leading=12, alignment=TA_LEFT, textColor=colors.HexColor('#526573'))
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=(8.27 * inch, 11.69 * inch), rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=50, title=report['title'], author='DocuMind')
    snapshot = report['snapshot']
    story = [Paragraph('DOCUMIND / EVIDENCE REVIEW', small), Spacer(1, 10), Paragraph(safe(report['title']), styles['Title']),
             Paragraph('Reviewed comparison report', styles['Heading2']),
             Paragraph(safe('Saved: ' + report['created_at'] + '\nReport: ' + report['id'] + '\nMethod: ' + snapshot['method']), small),
             Paragraph('STALE SOURCE REVISION - re-review required' if report['stale'] else 'Source revisions match at export time.', styles['Heading2']),
             Paragraph('Findings reflect a bounded evidence sample. They do not establish legal equivalence or whole-document completeness.', styles['BodyText']),
             HRFlowable(width='100%', thickness=1, color=colors.HexColor('#a9bdc9')), Spacer(1, 10),
             Paragraph('Summary', styles['Heading1'])]
    for label, count in snapshot['summary'].items():
        story.append(Paragraph(safe(f'{label.replace("_", " ").title()}: {count}'), styles['BodyText']))
    story.append(Paragraph('Scope and limitations', styles['Heading1']))
    limitations = list(snapshot['limitations'])
    limitations += [f"{item['file_id']}: {item['reason']}" for item in snapshot.get('extraction_limitations', [])]
    if snapshot.get('extraction_truncated'):
        limitations.append('Fact limit reached; only a partial sample is included.')
    limitations += ['Unsupported font characters are displayed as [U+XXXX]; JSON export preserves exact Unicode.', report['retention']]
    for text in limitations:
        story.append(Paragraph(safe(text), styles['BodyText']))
    sources = {s['evidence_id']: s for s in snapshot['sources']}
    story.append(Paragraph('Evidence-linked findings', styles['Heading1']))
    for index, finding in enumerate(snapshot['findings'], 1):
        story.append(KeepTogether([Paragraph(safe(f"{index}. {finding['topic']}"), styles['Heading2']),
                                    Paragraph(safe(finding['classification'].replace('_', ' ').title()), small)]))
        story.append(Paragraph(safe(finding['explanation']), styles['BodyText']))
        for document in finding['documents']:
            story.append(Paragraph(safe(document['filename']), styles['Heading2']))
            if not document['facts']:
                story.append(Paragraph('Not observed in the bounded evidence sample.', styles['BodyText']))
            for fact in document['facts']:
                story.append(Paragraph(safe(', '.join(fact['values'])), styles['BodyText']))
                source = sources.get(fact['evidence_id'])
                if source:
                    story.append(Paragraph(safe(source['excerpt']), quote))
                    story.append(Paragraph(safe(f"Source {source['evidence_id']} | {source['filename']} | page {source['page_number']}\nFile {source['file_id']} | chunk {source['source_id']}\nPublished run {source['processing_run_id']}\nContent SHA-256 {source['content_sha256']}"), small))
    story.append(Paragraph('Document revisions', styles['Heading1']))
    for source in snapshot['documents']:
        state = next(s for s in report['source_states'] if s['file_id'] == source['file_id'])
        story.append(Paragraph(safe(f"{source['filename']} | {source['file_id']}\nSaved version: {source['document_version']}\nCurrent version: {state['current_version']}\nState: {'STALE' if state['stale'] else 'matches'}"), small))
    def footer(canvas, _):
        canvas.saveState()
        canvas.setFont(FONT_NAME, 8)
        canvas.setFillColor(colors.HexColor('#526573'))
        canvas.drawString(48, 27, 'DocuMind | Private workspace report | Human review required')
        canvas.drawRightString(doc.pagesize[0] - 48, 27, f'Page {doc.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
