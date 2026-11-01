"""Offline known-context demo: two synthetic PDFs -> facts -> comparison -> report.

No ingestion, OCR, Atlas or provider calls are represented as live successes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(PYTHON_DOTENV_DISABLED='1', GEMINI_API_KEY='offline-demo-key',
                  MONGODB_URI='mongodb://127.0.0.1:1/?directConnection=true', DATABASE_NAME='offline_demo')


def deny_network(*args, **kwargs):
    raise RuntimeError('Network is disabled for this offline demo.')


socket.socket.connect = deny_network
socket.create_connection = deny_network

from bson import ObjectId
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from app.services.structured_facts import extract_chunk
from app.services.document_view import revision
from app.services.semantic_comparison import compare_facts
from app.services.comparison_reports import digest
from app.services.report_pdf import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    texts = [
        'Buyer: Aster Labs. Buyer must pay USD 100 by December 1, 2026. Buyer must disclose records. Supplier must deliver goods unless approval is withheld.',
        'Buyer: Aster Labs. Buyer is required to make payment of USD 200 by 2026-12-01. Buyer shall not disclose records. Supplier shall deliver goods unless approval is withheld.',
    ]
    facts, docs = [], []
    for index, text in enumerate(texts):
        file_id = f'{index + 1:024x}'
        filename = f'synthetic-{index + 1}.pdf'
        target = output / filename
        SimpleDocTemplate(str(target)).build([Paragraph(text, getSampleStyleSheet()['BodyText'])])
        content_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        doc = {'_id': ObjectId(file_id), 'filename': filename, 'status': 'completed',
               'active_processing_run_id': 'offline-known-context', 'content_sha256': content_hash}
        docs.append({'file_id': file_id, 'filename': filename, 'processing_run_id': doc['active_processing_run_id'],
                     'content_sha256': content_hash, 'document_version': revision(doc)})
        chunk = {'_id': ObjectId(f'{index + 100:024x}'), 'file_id': file_id, 'text': text,
                 'processing_run_id': doc['active_processing_run_id'], 'content_sha256': content_hash,
                 'chunk_index': 0, 'page_number': 1}
        for fact in extract_chunk(chunk, doc):
            assert text[fact['start_offset']:fact['end_offset']] == fact['quotation']
            facts.append({**fact, 'fact_id': 'f' + str(len(facts) + 1)})
    extraction = {'documents': docs, 'facts': facts, 'limits': {'demo_documents': 2, 'demo_pages_per_document': 1},
                  'limitations': [], 'truncated': False, 'notice': 'Synthetic known-context demo. Source PDFs and hashes are real local files; OCR text is supplied by the fixture. No live ingestion, OCR, Atlas or model evaluation was performed.'}
    snapshot = compare_facts(extraction, 'Synthetic payment and disclosure obligations')
    report = {'id': 'offline-synthetic-demo', 'title': 'Synthetic payment and disclosure review',
              'created_at': 'offline demo - not a saved database record', 'snapshot': snapshot,
              'review_digest': digest(snapshot), 'stale': False,
              'source_states': [{'file_id': doc['file_id'], 'saved_version': doc['document_version'], 'current_version': doc['document_version'], 'stale': False} for doc in docs],
              'retention': 'Local synthetic artifacts only; no database records created.'}
    (output / 'facts.json').write_text(json.dumps(extraction, indent=2))
    (output / 'comparison.json').write_text(json.dumps(snapshot, indent=2))
    (output / 'reviewed-report.json').write_text(json.dumps(report, indent=2))
    (output / 'reviewed-report.pdf').write_bytes(render(report))
    semantic = [finding for finding in snapshot['findings'] if finding['topic'].startswith('Normalized')]
    expected = {'supported_difference', 'possible_contradiction', 'insufficient_evidence'}
    assert {f['classification'] for f in semantic} == expected
    print(json.dumps({'mode': 'offline known-context; not live retrieval', 'facts': len(facts),
                      'exact_quote_checks_passed': len(facts), 'semantic_examples': len(semantic),
                      'classifications': [f['classification'] for f in semantic], 'provider_requests': 0}, indent=2))


if __name__ == '__main__':
    main()
