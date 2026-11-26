"""Combine a historical CSV with explicitly labelled supplementary reviews.

The original snapshot and database are never modified. Supplementary checks
are not automated model outputs, and their brand lists can be incomplete.
"""
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from src.exporter import safe_cell

SOURCE = Path('results/run-7-with-recovery.csv')
REVIEWS = Path('results/independent-review-2026-11-26.json')
DESTINATION = Path('results/run-7-reviewed.csv')


def main():
    reviews = json.loads(REVIEWS.read_text(encoding='utf-8'))
    domain_contacts = json.loads(Path('results/public-domain-contacts.json').read_text(encoding='utf-8'))
    with SOURCE.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    for key in ('review_method', 'review_date', 'review_note', 'public_contact_page'):
        if key not in fields:
            fields.append(key)
    for row in rows:
        review = reviews.get(row['url']) if row.get('analysis_status') != 'complete' else None
        row['review_method'] = 'supplementary_indexed_page' if review else ('ai_analysis' if row.get('analysis_status') == 'complete' else 'not_available')
        row['review_date'] = '2026-11-26' if review else ''
        row['review_note'] = review.get('note', '') if review else ''
        row['public_contact_page'] = review.get('contact_page', '') if review else ''
        if review:
            row['analysis_status'] = 'supplementary_review'
            row['relevance'] = review['relevance']
            row['brands'] = json.dumps(review.get('brands', []), ensure_ascii=False)
            # A separately researched public mailbox is not a model-extracted contact.
            if review.get('contact'):
                row['public_contact_candidate'] = review['contact']
                row['contact_candidate_source'] = review.get('contact_page', '')
        domain_contact = domain_contacts.get((urlsplit(row.get('url', '')).hostname or '').lower().removeprefix('www.'))
        if domain_contact and row.get('relevance') == 'yes':
            row['public_contact_candidate'] = domain_contact['email'] or row.get('public_contact_candidate', '')
            row['contact_candidate_source'] = domain_contact['source']
            row['public_contact_page'] = domain_contact['contact_page']
    with DESTINATION.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='raise')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_cell(row.get(key, '')) for key in fields})
    print(f'{DESTINATION}: {len(rows)} rows; original snapshot preserved.')


if __name__ == '__main__':
    main()
