import unittest
import importlib
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

metrics_mod = importlib.import_module("pages.3_metrics")
canonicalize_skill_label = metrics_mod.canonicalize_skill_label
classify_red_flag = metrics_mod.classify_red_flag
import evaluator


class TestIndustryAgnosticSkippy(unittest.TestCase):
    def test_cross_industry_skill_canonicalization(self):
        # Healthcare & Medicine
        self.assertEqual(
            canonicalize_skill_label("epic ehr"),
            "Electronic Health Records (EHR / Epic / Cerner)"
        )
        self.assertEqual(
            canonicalize_skill_label("hipaa"),
            "HIPAA Compliance & Patient Privacy"
        )
        self.assertEqual(
            canonicalize_skill_label("bls"),
            "Basic Life Support (BLS)"
        )
        self.assertEqual(
            canonicalize_skill_label("patient triage"),
            "Patient Triage & Clinical Assessment"
        )

        # Legal & Compliance
        self.assertEqual(
            canonicalize_skill_label("westlaw"),
            "Legal Research (Westlaw / LexisNexis)"
        )
        self.assertEqual(
            canonicalize_skill_label("clm"),
            "Contract Drafting & Lifecycle Management (CLM)"
        )
        self.assertEqual(
            canonicalize_skill_label("litigation"),
            "Litigation & e-Discovery"
        )

        # Logistics & Supply Chain
        self.assertEqual(
            canonicalize_skill_label("wms"),
            "Warehouse Management Systems (WMS)"
        )
        self.assertEqual(
            canonicalize_skill_label("tms"),
            "Transportation Management Systems (TMS)"
        )
        self.assertEqual(
            canonicalize_skill_label("supply chain"),
            "Supply Chain Management (SCM)"
        )
        self.assertEqual(
            canonicalize_skill_label("six sigma"),
            "Lean / Six Sigma"
        )

        # HR & People Ops
        self.assertEqual(
            canonicalize_skill_label("workday"),
            "HRIS (Workday / ADP)"
        )
        self.assertEqual(
            canonicalize_skill_label("talent acquisition"),
            "Talent Acquisition & Full-Cycle Recruiting"
        )
        self.assertEqual(
            canonicalize_skill_label("shrm"),
            "SHRM / HRCI Certification"
        )

        # Finance & Accounting
        self.assertEqual(
            canonicalize_skill_label("gaap"),
            "GAAP / IFRS Accounting Standards"
        )
        self.assertEqual(
            canonicalize_skill_label("financial modeling"),
            "Financial Modeling & FP&A"
        )
        self.assertEqual(
            canonicalize_skill_label("cpa"),
            "CPA / Financial Audit"
        )

        # Tech & Security (backward compatibility)
        self.assertEqual(
            canonicalize_skill_label("sentinel"),
            "Microsoft Sentinel"
        )
        self.assertEqual(
            canonicalize_skill_label("security+"),
            "CompTIA Security+"
        )

    def test_universal_acronym_preservation(self):
        # Even unlisted compound phrases should preserve industry acronyms in uppercase
        self.assertIn("OSHA", canonicalize_skill_label("osha standards compliance"))
        self.assertIn("HIPAA", canonicalize_skill_label("advanced hipaa auditing"))
        self.assertIn("FIFO", canonicalize_skill_label("fifo inventory methodology"))

    def test_cross_industry_red_flags(self):
        # Healthcare license gate
        cat_rn = classify_red_flag("Disqualified: Mandatory Active RN License required")
        self.assertIn("Degree / License", cat_rn)

        # Legal bar admission gate
        cat_bar = classify_red_flag("Disqualified: State bar admission required")
        self.assertIn("Degree / License", cat_bar)

        # Clinical / Domain platform SME expectation
        cat_plat = classify_red_flag("Missing required clinical platform: Epic EHR")
        self.assertIn("Specialized Platform", cat_plat)

        # Logistics / Security clearance gate
        cat_clear = classify_red_flag("Requires active Secret security clearance")
        self.assertIn("Clearance", cat_clear)

        # Healthcare / On-call rotation
        cat_shift = classify_red_flag("Requires 12-hour night shift work and weekend rotation")
        self.assertIn("On-Call Rotation", cat_shift)

    def test_ats_section_headings_cover_diverse_fields(self):
        self.assertIn("CLINICAL EXPERIENCE", evaluator._ATS_SECTION_NAMES)
        self.assertIn("LEGAL EXPERIENCE", evaluator._ATS_SECTION_NAMES)
        self.assertIn("BAR ADMISSIONS", evaluator._ATS_SECTION_NAMES)
        self.assertIn("LICENSURE & CREDENTIALS", evaluator._ATS_SECTION_NAMES)
        self.assertIn("REPRESENTATIVE MATTERS", evaluator._ATS_SECTION_NAMES)
        self.assertIn("TEACHING EXPERIENCE", evaluator._ATS_SECTION_NAMES)


if __name__ == "__main__":
    unittest.main()
