"""Regulatory mapping entries must cite verified sources or say they are unverified."""
import unittest

from fraudlens.operations.guidance import guidance_response

FIELDS = {"issuer", "source", "url", "date", "status", "what_it_requires", "how_fraudlens_models_it", "not_covered"}


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.entries = guidance_response()["requirements"]

    def test_every_entry_has_the_mapping_fields(self):
        self.assertGreaterEqual(len(self.entries), 5)
        for entry in self.entries:
            self.assertEqual(set(entry), FIELDS, entry["source"])
            for key in FIELDS - {"url"}:
                self.assertTrue(entry[key].strip(), (entry["source"], key))

    def test_covers_i4c_ncrp_rbi_and_npci(self):
        self.assertEqual({e["issuer"] for e in self.entries}, {"I4C (Ministry of Home Affairs)", "Reserve Bank of India", "NPCI"})
        sources = " ".join(e["source"] for e in self.entries)
        for phrase in ("Citizen Financial Cyber Fraud Reporting and Management System", "National Cyber Crime Reporting Portal",
                       "Fraud Risk Management", "Limiting Liability of Customers"):
            self.assertIn(phrase, sources)

    def test_unverified_entries_are_labelled_and_verified_ones_link_primary_domains(self):
        for entry in self.entries:
            if entry["url"] is None:
                self.assertEqual(entry["status"], "modelled on (unverified)", entry["source"])
            else:
                self.assertTrue(entry["status"].startswith("Verified"), entry["source"])
                self.assertRegex(entry["url"], r"^https://(www\.)?(rbi\.org\.in|pib\.gov\.in|cybercrime\.gov\.in|npci\.org\.in)/")
        self.assertTrue(any(e["issuer"] == "NPCI" and e["url"] is None for e in self.entries))


if __name__ == "__main__":
    unittest.main()
