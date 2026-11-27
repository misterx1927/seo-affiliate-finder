import csv
import tempfile
import unittest
from pathlib import Path
from src.analyzer import AnalysisError, validate_analysis
from src.database import connect, replace_keyword_results
from src.exporter import export_observations, export_partial_observations, safe_cell, serp_provenance

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.text = "Best casinos: Maple Casino and Blue Casino. Contact editor@example.com. Independent casino reviews."
        self.valid = {"relevance": "yes", "brands": ["Maple Casino"], "contact": "editor@example.com", "evidence": "Independent casino reviews"}

    def test_valid_grounded_response(self):
        self.assertEqual(validate_analysis(self.valid, self.text).brands, ("Maple Casino",))

    def test_unverified_claims_are_rejected(self):
        for field, value in (("brands", ["Imaginary Casino"]), ("contact", "fake@example.com"), ("evidence", "Invented fact")):
            payload = dict(self.valid, **{field: value})
            with self.subTest(field=field), self.assertRaises(AnalysisError): validate_analysis(payload, self.text)

    def test_brand_must_be_a_complete_name_not_part_of_another_word(self):
        text = "PartyCasino is an operator. Spin exists only inside Spinomenal. Independent reviews."
        base = {"relevance": "needs_review", "brands": [], "contact": None, "evidence": "Independent reviews"}
        for brand in ("Party", "Spin"):
            # Spin is also present on its own in this particular sentence; isolate the embedded form.
            example = text.replace("Spin exists only inside ", "")
            with self.subTest(brand=brand), self.assertRaises(AnalysisError):
                validate_analysis(dict(base, brands=[brand]), example)
        self.assertEqual(validate_analysis(dict(base, brands=["PartyCasino"]), text).brands, ("PartyCasino",))

    def test_brand_word_boundaries_allow_punctuation_and_repeated_occurrences(self):
        text = "Spinomenal is a provider; (Spin) is a casino. Independent reviews."
        payload = {"relevance": "yes", "brands": ["Spin"], "contact": None, "evidence": "Independent reviews"}
        self.assertEqual(validate_analysis(payload, text).brands, ("Spin",))

    def test_urls_do_not_count_as_brand_mentions_but_visible_link_labels_do(self):
        payload = {"relevance": "yes", "brands": ["Casino.org"], "contact": None, "evidence": "Independent reviews"}
        url_only = "Independent reviews [Read more](https://www.casino.org/canada/new/)"
        with self.assertRaises(AnalysisError):
            validate_analysis(payload, url_only)
        label = "Independent reviews [Casino.org](https://www.casino.org/canada/new/)"
        self.assertEqual(validate_analysis(payload, label).brands, ("Casino.org",))

    def test_bad_schema_is_rejected(self):
        with self.assertRaises(AnalysisError): validate_analysis({"relevance": "yes"}, self.text)
        with self.assertRaises(AnalysisError): validate_analysis(dict(self.valid, relevance="maybe"), self.text)

    def test_email_protection_placeholder_is_not_a_contact(self):
        text = self.text + " [email protected]"
        result = validate_analysis(dict(self.valid, contact="[email protected]"), text)
        self.assertIsNone(result.contact)

    def test_contact_label_is_not_a_usable_contact(self):
        text = self.text + " Contact us"
        self.assertIsNone(validate_analysis(dict(self.valid, contact="Contact us"), text).contact)

    def test_email_cannot_be_a_suffix_of_a_different_address(self):
        text = "Mail chiefeditor@example.com. Independent casino reviews. Maple Casino."
        with self.assertRaises(AnalysisError):
            validate_analysis(self.valid, text)

    def test_public_phone_and_contact_url_are_accepted(self):
        for contact in ("+1 (416) 555-0133", "https://example.com/contact"):
            with self.subTest(contact=contact):
                text = self.text + " " + contact
                self.assertEqual(validate_analysis(dict(self.valid, contact=contact), text).contact, contact)

    def test_brand_duplicates_ignore_case_and_whitespace(self):
        payload = dict(self.valid, brands=["Maple Casino", "maple   casino", "Blue Casino"])
        result = validate_analysis(payload, self.text)
        self.assertEqual(result.brands, ("Maple Casino", "Blue Casino"))

    def test_brand_duplicates_allow_space_at_digit_letter_boundary_only(self):
        text = "21 Casino and 21Casino are compared with 21 Casino Deluxe and 2 1 Casino. Independent reviews."
        payload = {"relevance": "yes", "brands": ["21 Casino", "21Casino", "21 Casino Deluxe", "2 1 Casino"],
                   "contact": None, "evidence": "Independent reviews"}
        result = validate_analysis(payload, text)
        self.assertEqual(result.brands, ("21 Casino", "21 Casino Deluxe", "2 1 Casino"))

class ExportTests(unittest.TestCase):
    def test_same_day_runs_export_their_own_positions_and_legacy_fallback(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        with conn:
            for run_id in (1, 2):
                conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES (?, 'now', 'live', 'complete')", (run_id,))
                conn.execute('INSERT INTO run_analysis_tracking(run_id) VALUES (?)', (run_id,))
                replace_keyword_results(conn, '2026-11-27', 'q', [{'position': 1, 'url': f'https://example{run_id}.com'}], run_id)
            conn.execute("INSERT INTO run_page_analysis(run_id,url,status,relevance) VALUES (1,'https://example1.com/','complete','yes')")
            # A legacy keyword from the same run has no archived rows.
            conn.execute("INSERT INTO observations VALUES ('2026-11-27','legacy',1,'https://legacy.example/','legacy.example',1)")
        path = Path('data/test-same-day-export.csv')
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.assertEqual(export_observations(conn, path, run_id=1), 2)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = {row['keyword']: row for row in csv.DictReader(stream)}
        self.assertEqual((rows['q']['domain'], rows['q']['relevance']), ('example1.com', 'yes'))
        self.assertEqual(rows['legacy']['domain'], 'legacy.example')
        self.assertEqual(export_observations(conn, path), 2)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            current = {row['keyword']: row for row in csv.DictReader(stream)}
        self.assertEqual(current['q']['domain'], 'example2.com')

    def test_tracked_run_exports_its_own_analysis_without_borrowing_current_page(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        url = 'https://publisher.example/review'
        with conn:
            for run_id in (1, 2, 3):
                conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES (?, 'now', 'live', 'partial')", (run_id,))
                conn.execute('INSERT INTO run_analysis_tracking(run_id) VALUES (?)', (run_id,))
                replace_keyword_results(conn, f'2026-11-{run_id + 20}', 'q', [{'position': 1, 'url': url}], run_id)
                conn.execute('INSERT INTO partial_observations VALUES (?, ?, ?, ?, ?, ?)', (run_id, f'2026-11-{run_id + 20}', 'partial', 1, url, 'publisher.example'))
            conn.execute("INSERT INTO pages(url,status,relevance,brands_json,contact) VALUES (?, 'complete', 'no', '[\"Current\"]', 'current@publisher.example')", (url,))
            conn.execute("INSERT INTO run_page_analysis(run_id,url,status,relevance,brands_json,contact) VALUES (1, ?, 'complete', 'yes', '[\"Old\"]', 'old@publisher.example')", (url,))
            conn.execute("INSERT INTO run_page_analysis(run_id,url,status,error) VALUES (2, ?, 'needs_review', 'Unavailable')", (url,))
        path = Path('data/test-history-export.csv')
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        for exporter in (export_observations, export_partial_observations):
            with self.subTest(exporter=exporter.__name__):
                for run_id, status, relevance, contact in ((1, 'complete', 'yes', 'old@publisher.example'), (2, 'needs_review', '', ''), (3, 'pending', '', '')):
                    exporter(conn, path, run_id=run_id)
                    with path.open(encoding='utf-8-sig', newline='') as stream:
                        row = next(csv.DictReader(stream))
                    self.assertEqual((row['analysis_status'], row['relevance'], row['contact']), (status, relevance, contact))
                    self.assertEqual(row['page_source'], 'not_recorded')

    def test_restored_result_provenance_is_distinguished(self):
        self.assertEqual(serp_provenance(3, '[1, 3]', 1), 'restored_from_google_web')
        self.assertEqual(serp_provenance(2, '[1, 3]', 1), 'original_or_verification_unavailable')
        self.assertEqual(serp_provenance(2, '[]', 0), 'verification_not_requested')
        self.assertEqual(serp_provenance(2, None, None), 'unknown')
    def test_leading_control_characters_are_escaped(self):
        self.assertEqual(safe_cell("\ttext"), "'\ttext")
        self.assertEqual(safe_cell("  =1+1"), "'  =1+1")
    def test_partial_export_limits_rows_to_requested_run(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        with conn:
            for run_id in (1, 2):
                conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES (?, 'now', 'live', 'partial')", (run_id,))
                conn.execute("INSERT INTO partial_observations VALUES (?, '2026-11-25', 'q', 1, 'https://example.com/', 'example.com')", (run_id,))
        path = Path("data/test-partial-export.csv")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.assertEqual(export_partial_observations(conn, path, run_id=2), 1)
        with path.open(encoding="utf-8-sig", newline="") as file: rows = list(csv.reader(file))
        self.assertEqual(rows[1][0], "2")

    def test_complete_export_limits_rows_to_requested_run(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        with conn:
            for run_id in (1, 2):
                conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES (?, 'now', 'live', 'complete')", (run_id,))
                replace_keyword_results(conn, f'2026-11-{run_id + 20}', 'q', [{'position': 1, 'url': f'https://example{run_id}.com'}], run_id)
        path = Path('data/test-run-export.csv')
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.assertEqual(export_observations(conn, path, run_id=2), 1)
        with path.open(encoding='utf-8-sig', newline='') as stream: rows = list(csv.reader(stream))
        self.assertEqual(rows[1][4], 'example2.com')

    def test_export_and_spreadsheet_injection(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        replace_keyword_results(conn, "2026-11-24", "=1+1", [{"position": 1, "url": "https://example.com"}])
        path = Path("data/test-export.csv")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.assertEqual(export_observations(conn, path), 1)
        with path.open(encoding="utf-8-sig", newline="") as f: rows = list(csv.reader(f))
        self.assertEqual(rows[1][1], "'=1+1")
        self.assertEqual(rows[1][3], "https://example.com/")

    def test_contact_candidate_is_separate_from_model_contact(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        replace_keyword_results(conn, '2026-11-25', 'q', [{'position': 1, 'url': 'https://publisher.example/review'}])
        with conn:
            conn.execute("INSERT INTO outreach_contact_candidates VALUES(?, ?, ?, ?)", ('https://publisher.example/review', 'https://publisher.example/contact', 'press@publisher.example', '2026-11-26'))
        path = Path('data/test-contact-export.csv')
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        export_observations(conn, path)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['contact'], '')
        self.assertEqual(row['public_contact_candidate'], 'press@publisher.example')
        self.assertEqual(row['contact_candidate_source'], 'https://publisher.example/contact')

    def test_export_retains_analysis_version(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        replace_keyword_results(conn, '2026-11-25', 'q', [{'position': 1, 'url': 'https://publisher.example/review'}])
        with conn:
            conn.execute("INSERT INTO pages(url, status, analysis_version) VALUES (?, 'complete', 'v7')", ('https://publisher.example/review',))
        path = Path('data/test-version-export.csv')
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        export_observations(conn, path)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(next(csv.DictReader(stream))['analysis_version'], 'v7')

if __name__ == "__main__": unittest.main()
