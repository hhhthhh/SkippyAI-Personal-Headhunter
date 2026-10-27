import unittest
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import career_compass
import database as db


class TestCareerCompass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db_path = db.DB_PATH
        cls.orig_db_file = db.DB_FILE
        cls.orig_profile_json = getattr(db, "PROFILE_JSON_FILE", "profile_alignment.json")
        cls.test_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_career_compass_temp.db"))
        cls.test_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_profile_alignment_temp.json"))

    def setUp(self):
        db.DB_PATH = self.test_db
        db.DB_FILE = self.test_db
        db.PROFILE_JSON_FILE = self.test_json
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.orig_db_path
        db.DB_FILE = self.orig_db_file
        db.PROFILE_JSON_FILE = self.orig_profile_json
        for path in [self.test_db, self.test_json]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.orig_db_path
        db.DB_FILE = cls.orig_db_file
        db.PROFILE_JSON_FILE = cls.orig_profile_json
        for path in [cls.test_db, cls.test_json]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def test_first_responder_scoring(self):
        """Tests that choosing fire/EMS options scores primary first_responder with life safety gates."""
        # Index 0 for all questions is first responder
        answers = {q["id"]: 0 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        profile = career_compass.score_quiz_responses(answers)

        self.assertEqual(profile["primary_domain"], "first_responder")
        self.assertIn("Emergency Response", profile["archetype_title"])
        self.assertGreater(profile["scores"]["first_responder"], 70.0)
        # Check compliance gates
        gates_str = " ".join(profile["compliance_gates"])
        self.assertIn("NREMT", gates_str)
        self.assertIn("NFPA", gates_str)

    def test_military_defense_scoring(self):
        """Tests that choosing military tactical options scores primary military_defense with clearance gates."""
        # Index 1 for all questions is military/defense
        answers = {q["id"]: 1 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        profile = career_compass.score_quiz_responses(answers)

        self.assertEqual(profile["primary_domain"], "military_defense")
        self.assertIn("Defense", profile["archetype_title"])
        self.assertGreater(profile["scores"]["military_defense"], 70.0)
        # Check security clearance gate
        gates_str = " ".join(profile["compliance_gates"])
        self.assertIn("Security Clearance", gates_str)
        self.assertIn("DD-214", gates_str)

    def test_public_sector_scoring(self):
        """Tests that choosing government/civil service options scores primary public_sector with FAR gates."""
        # Index 2 for all questions is public sector
        answers = {q["id"]: 2 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        profile = career_compass.score_quiz_responses(answers)

        self.assertEqual(profile["primary_domain"], "public_sector")
        self.assertIn("Public Sector", profile["archetype_title"])
        self.assertGreater(profile["scores"]["public_sector"], 70.0)
        gates_str = " ".join(profile["compliance_gates"])
        self.assertIn("Civil Service", gates_str)

    def test_skilled_trades_scoring(self):
        """Tests that choosing electrical/HVAC options scores primary trades_construction with Journeyman gates."""
        # Index 3 for all questions is skilled trades
        answers = {q["id"]: 3 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        profile = career_compass.score_quiz_responses(answers)

        self.assertEqual(profile["primary_domain"], "trades_construction")
        self.assertIn("Trades", profile["archetype_title"])
        self.assertGreater(profile["scores"]["trades_construction"], 70.0)
        gates_str = " ".join(profile["compliance_gates"])
        self.assertIn("Journeyman", gates_str)
        self.assertIn("EPA 608", gates_str)

    def test_cdl_transport_scoring(self):
        """Tests that choosing freight/trucking options scores primary logistics_transport with CDL gates."""
        # Index 5 for all questions is logistics/transport
        answers = {q["id"]: 5 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        profile = career_compass.score_quiz_responses(answers)

        self.assertEqual(profile["primary_domain"], "logistics_transport")
        self.assertIn("Fleet", profile["archetype_title"])
        self.assertGreater(profile["scores"]["logistics_transport"], 70.0)
        gates_str = " ".join(profile["compliance_gates"])
        self.assertIn("Commercial Driver's License", gates_str)
        self.assertIn("DOT", gates_str)

    def test_hybrid_archetype_synthesis(self):
        """Tests cross-domain hybrid detection (e.g. military + logistics, trades + software)."""
        # Mix military (idx 1) and transport (idx 5)
        answers_mil_logistics = {
            "q1_calling": 1,  # Military
            "q2_environment": 1,  # Military
            "q3_tools": 5,  # Telematics / Logistics
            "q4_crisis": 5,  # Reroute freight
            "q5_win": 1,  # Mission accomplished
            "q6_standards": 1,  # Security clearance
            "q7_horizon": 5,  # Fleet / Logistics director
        }
        profile = career_compass.score_quiz_responses(answers_mil_logistics)
        self.assertEqual(profile["primary_domain"], "military_defense")
        self.assertEqual(profile["secondary_domain"], "logistics_transport")
        self.assertIn("Defense Logistics", profile["archetype_title"])

        # Mix trades (idx 3) and software (idx 9)
        answers_mechatronics = {
            "q1_calling": 3,  # Trades
            "q2_environment": 3,  # Job site
            "q3_tools": 3,  # Multimeters
            "q4_crisis": 3,  # Shut off breaker / fix
            "q5_win": 9,  # Code shipped
            "q6_standards": 9,  # Git / Tech certs
            "q7_horizon": 9,  # Lead software / systems
        }
        profile_mech = career_compass.score_quiz_responses(answers_mechatronics)
        self.assertEqual(profile_mech["primary_domain"], "trades_construction")
        self.assertEqual(profile_mech["secondary_domain"], "software_engineering")
        self.assertIn("Automation", profile_mech["archetype_title"])

    def test_resume_auto_detection_veteran(self):
        """Verifies military resume auto-detects military_defense."""
        veteran_resume = """
        John Doe, SSG (E-6)
        Combat Operations NCO | Active Secret Clearance | DD-214 Honorable Discharge
        - Planned tactical missions, managed $4M in weapons systems and C4ISR communications equipment.
        - Supervised 14-person squad during high-intensity training exercises.
        - Military Occupational Specialty: 11B Infantry Squad Leader.
        """
        profile = career_compass.auto_detect_alignment_from_resume(veteran_resume)
        self.assertEqual(profile["primary_domain"], "military_defense")
        self.assertIn("Defense", profile["archetype_title"])

    def test_resume_auto_detection_first_responder(self):
        """Verifies paramedic/firefighter resume auto-detects first_responder."""
        fire_resume = """
        Jane Smith, Lead Paramedic / Firefighter
        Certifications: NREMT-Paramedic, NFPA Firefighter I/II, HazMat Operations, EVOC, ACLS, PALS
        - Responded to over 800 emergency 911 calls, establishing Incident Command (ICS/NIMS) on structure fires.
        - Administered advanced field emergency life support and acute trauma stabilization.
        """
        profile = career_compass.auto_detect_alignment_from_resume(fire_resume)
        self.assertEqual(profile["primary_domain"], "first_responder")
        self.assertIn("Emergency", profile["archetype_title"])

    def test_resume_auto_detection_blue_collar_cdl(self):
        """Verifies truck driver resume auto-detects logistics_transport."""
        cdl_resume = """
        Marcus Vance, Professional CDL-A Commercial Driver
        Credentials: CDL Class A with Tanker (N) and HazMat (X) Endorsements, Valid DOT Medical Card
        - Over 600,000 accident-free highway miles hauling regional refrigerated and dry van freight.
        - Maintained 100% compliance with FMCSA and Electronic Logging Devices (ELD) regulations.
        - Forklift certified for loading and cross-dock pallet staging.
        """
        profile = career_compass.auto_detect_alignment_from_resume(cdl_resume)
        self.assertEqual(profile["primary_domain"], "logistics_transport")
        self.assertIn("Fleet", profile["archetype_title"])

    def test_adapted_custom_prompt_generation(self):
        """Verifies that generated custom prompt incorporates archetype title and compliance gates."""
        profile = {
            "primary_title": "Skilled Trades, Construction & Field Maintenance",
            "archetype_title": "Master Electrician & Electrical Specialist",
            "compliance_gates": [
                "State Journeyman or Master Electrician License",
                "EPA 608 Universal Certification",
                "OSHA 30-Hour Safety Certification",
            ]
        }
        prompt = career_compass.generate_adapted_custom_prompt(profile)
        self.assertIn("Master Electrician & Electrical Specialist", prompt)
        self.assertIn("EPA 608 Universal Certification", prompt)
        self.assertIn("State Journeyman", prompt)
        self.assertIn("eligibility_gate", prompt)

    def test_database_profile_persistence_roundtrip(self):
        """Verifies SQLite save and load roundtrip for user profile."""
        test_profile = {
            "primary_domain": "military_defense",
            "secondary_domain": "cybersecurity",
            "primary_title": "Military Operations, Defense & Tactical Systems",
            "secondary_title": "Cybersecurity, Threat Defense & Digital Forensics",
            "archetype_title": "Cleared Defense Cyber Analyst & Threat Specialist",
            "archetype_description": "Military-grade cyber defender protecting defense networks.",
            "scores": {"military_defense": 55.0, "cybersecurity": 45.0},
            "keywords": ["secret", "top secret", "c4isr", "siem", "splunk"],
            "search_queries": ["Cleared Defense Analyst", "SOC Analyst"],
            "compliance_gates": ["Active Security Clearance (Top Secret)"],
            "adapted_prompt": "Custom Evaluation Prompt",
        }
        saved = db.save_user_profile(test_profile)
        self.assertTrue(saved)

        loaded = db.load_user_profile()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["primary_domain"], "military_defense")
        self.assertEqual(loaded["secondary_domain"], "cybersecurity")
        self.assertEqual(loaded["archetype_title"], "Cleared Defense Cyber Analyst & Threat Specialist")
        self.assertEqual(loaded["scores"].get("military_defense"), 55.0)
        self.assertEqual(len(loaded["keywords"]), 5)

    def test_radar_chart_figure_generation(self):
        """Verifies that render_alignment_radar_chart returns a valid Plotly Figure with linear polygonal grid."""
        scores = {
            "first_responder": 40.0,
            "military_defense": 30.0,
            "healthcare_clinical": 20.0,
            "trades_construction": 10.0,
            "protective_services": 5.0,
        }
        fig = career_compass.render_alignment_radar_chart(scores)
        self.assertIsNotNone(fig)
        self.assertTrue(hasattr(fig, "data"))
        self.assertGreater(len(fig.data), 0)
        # Verify Option C: gridshape must be 'linear' for geometric polygon
        self.assertEqual(fig.layout.polar.gridshape, "linear")
        # 5 distinct categories + 1 closed loop = 6 elements
        self.assertEqual(len(fig.data[0].theta), 6)

    def test_radar_chart_dynamic_polygon_scaling(self):
        """Verifies dynamic polygonal scaling across 3 (triangle), 5 (pentagon), and 7 (heptagon) vertices."""
        # 3 vertices (Triangle)
        triangle_scores = {"A": 50.0, "B": 30.0, "C": 20.0}
        fig_tri = career_compass.render_alignment_radar_chart(triangle_scores)
        self.assertEqual(fig_tri.layout.polar.gridshape, "linear")
        self.assertEqual(len(fig_tri.data[0].theta), 4)  # 3 vertices + closure

        # 7 vertices (Heptagon)
        heptagon_scores = {f"Track_{i}": 10.0 + i for i in range(1, 8)}
        fig_hep = career_compass.render_alignment_radar_chart(heptagon_scores)
        self.assertEqual(fig_hep.layout.polar.gridshape, "linear")
        self.assertEqual(len(fig_hep.data[0].theta), 8)  # 7 vertices + closure

        # >7 vertices: capped at 7 for visual polygon clarity
        wide_scores = {f"Domain_{i}": 10.0 + i for i in range(1, 14)}
        fig_wide = career_compass.render_alignment_radar_chart(wide_scores)
        self.assertEqual(len(fig_wide.data[0].theta), 8)  # Capped at 7 + closure

    def test_ai_archetype_profile_schema(self):
        """Validates AIArchetypeProfile Pydantic schema validation."""
        sample_data = {
            "archetype_title": "Autonomous Subsea Robotics Specialist",
            "primary_domain": "Marine Robotics",
            "secondary_domain": "Subsea Engineering",
            "archetype_description": "Designs and pilots autonomous underwater vehicles for deep ocean exploration.",
            "core_keywords": ["ROV", "AUV", "acoustic telemetry", "side-scan sonar", "manipulator arm", "pressure housing"],
            "compliance_gates": ["IMCA ROV Pilot Cert", "BOSIET Offshore Safety", "FAA Part 107"],
            "recommended_search_queries": ["ROV Pilot", "Subsea Robotics Engineer", "Oceanographic Technician"],
            "rubric_focus": "Verified deepwater deployment hours, high-pressure hydraulic repair, and tether telemetry."
        }
        profile_obj = career_compass.AIArchetypeProfile(**sample_data)
        self.assertEqual(profile_obj.archetype_title, "Autonomous Subsea Robotics Specialist")
        self.assertEqual(len(profile_obj.core_keywords), 6)
        self.assertIn("BOSIET", profile_obj.compliance_gates[1])

    def test_detect_alignment_with_ai_mocked(self):
        """Verifies detect_alignment_with_ai parses LLM response and constructs profile correctly."""
        from unittest.mock import patch, MagicMock

        mock_profile = career_compass.AIArchetypeProfile(
            archetype_title="Master Watchmaker & Horologist",
            primary_domain="Precision Horology",
            secondary_domain="Micro-Mechanical Engineering",
            archetype_description="Specialist in micro-mechanical escapements, hairspring regulation, and chronometer restoration.",
            core_keywords=["escapement", "hairspring", "tourbillon", "poising", "chronometer", "jeweled bearings", "loup"],
            compliance_gates=["WOSTEP Certification", "AWCI CW21 Certification"],
            recommended_search_queries=["Master Watchmaker", "Horological Conservator", "Watch Technician"],
            rubric_focus="Precision mechanical tolerance inspection (sub-micron) and movement overhaul experience."
        )

        mock_llm_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_profile.model_dump_json()
        mock_llm_response.choices = [mock_choice]

        with patch("evaluator.call_unified_llm", return_value=mock_llm_response):
            result = career_compass.detect_alignment_with_ai(
                resume_text="Over 10 years crafting mechanical watch movements and tourbillons.",
                industry_hint="Precision Watchmaking",
                model_choice="Mock Model",
                api_key="mock_key"
            )

        self.assertEqual(result["archetype_title"], "Master Watchmaker & Horologist")
        self.assertEqual(result["primary_title"], "Precision Horology")
        self.assertTrue(result["ai_synthesized"])
        self.assertIn("escapement", result["keywords"])
        self.assertIn("WOSTEP Certification", result["compliance_gates"])
        self.assertIn("Precision Horology", result["scores"])

    def test_niche_prompt_generation_with_rubric(self):
        """Verifies custom rubric focus and bespoke gates are woven into generated custom prompt."""
        niche_profile = {
            "archetype_title": "Industrial Ammonia Refrigeration Engineer",
            "primary_title": "Industrial Refrigeration",
            "archetype_description": "Maintains cold-chain ammonia chillers with zero-leak protocols.",
            "compliance_gates": ["EPA Universal 608", "RETA CARO Certification", "OSHA PSM Hazmat"],
            "rubric_focus": "Process Safety Management (PSM), screw compressor overhauls, and purge unit calibration."
        }
        prompt = career_compass.generate_adapted_custom_prompt(niche_profile)
        self.assertIn("Industrial Ammonia Refrigeration Engineer", prompt)
        self.assertIn("EPA Universal 608", prompt)
        self.assertIn("RETA CARO Certification", prompt)
        self.assertIn("Specialized Industry Rubric: Process Safety Management", prompt)
        self.assertIn("**Operational Mission:** Maintains cold-chain ammonia chillers", prompt)

    def test_niche_database_persistence_roundtrip(self):
        """Verifies DB persistence of AI-synthesized archetype and rubric focus."""
        niche_data = {
            "primary_domain": "ammonia_refrigeration",
            "secondary_domain": "industrial_maintenance",
            "primary_title": "Ammonia Refrigeration",
            "secondary_title": "Industrial Maintenance",
            "archetype_title": "Industrial Ammonia Refrigeration Engineer",
            "archetype_description": "Maintains cold-chain ammonia chillers with zero-leak protocols.",
            "scores": {"Ammonia Refrigeration": 75.0, "Industrial Maintenance": 25.0},
            "keywords": ["ammonia", "r-717", "frick compressors", "condensers"],
            "search_queries": ["Ammonia Refrigeration Technician", "PSM Coordinator"],
            "compliance_gates": ["RETA CARO", "EPA Universal 608"],
            "adapted_prompt": "Specialized Ammonia Prompt",
            "ai_synthesized": True,
            "rubric_focus": "Process Safety Management and screw compressor overhaul.",
        }
        saved = db.save_user_profile(niche_data)
        self.assertTrue(saved)

        loaded = db.load_user_profile()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["archetype_title"], "Industrial Ammonia Refrigeration Engineer")
        self.assertTrue(loaded.get("ai_synthesized"))
        self.assertEqual(loaded.get("rubric_focus"), "Process Safety Management and screw compressor overhaul.")
        self.assertEqual(len(loaded["compliance_gates"]), 2)

    def test_radar_chart_custom_niche_domains(self):
        """Ensures radar chart never crashes with KeyError when arbitrary niche domains are passed."""
        niche_scores = {
            "Autonomous Robotics": 70.0,
            "Deep Ocean Exploration": 30.0,
        }
        fig = career_compass.render_alignment_radar_chart(niche_scores)
        self.assertIsNotNone(fig)
        self.assertTrue(hasattr(fig, "data"))
        self.assertGreater(len(fig.data), 0)

    def test_self_healing_sqlite_from_json(self):
        """Verifies that if SQLite user_profile is deleted/empty, load_user_profile restores it from JSON."""
        backup_data = {
            "primary_domain": "robotics",
            "primary_title": "Robotics Engineering",
            "archetype_title": "Autonomous Systems Engineer",
            "scores": {"Robotics Engineering": 90.0},
            "keywords": ["ros2", "slam"],
            "search_queries": ["Robotics Engineer"],
            "compliance_gates": [],
            "ai_synthesized": True
        }
        # Write directly to test_json
        with open(self.test_json, "w", encoding="utf-8") as f:
            json.dump(backup_data, f)

        # Clear SQLite user_profile table
        conn = db.get_connection()
        with conn:
            conn.execute("DELETE FROM user_profile WHERE id = 'default_user'")
        conn.close()

        # load_user_profile should restore from JSON and self-heal SQLite
        loaded = db.load_user_profile()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["archetype_title"], "Autonomous Systems Engineer")

        # Verify SQLite row was recreated
        conn2 = db.get_connection()
        cur = conn2.cursor()
        cur.execute("SELECT archetype_title FROM user_profile WHERE id = 'default_user'")
        row = cur.fetchone()
        conn2.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Autonomous Systems Engineer")

    def test_custom_skills_persistence_db_and_json(self):
        """Verifies saving and loading profile with custom skills preserves them in SQLite and JSON."""
        profile = {
            "primary_domain": "software_engineering",
            "primary_title": "Software Engineering",
            "archetype_title": "Full Stack Engineer",
            "scores": {"software_engineering": 100.0},
            "keywords": ["Python", "FastAPI", "Kubernetes"],
            "custom_skills": ["FastAPI", "Kubernetes"],
            "search_queries": ["Software Engineer"],
            "compliance_gates": [],
        }
        saved = db.save_user_profile(profile)
        self.assertTrue(saved)

        loaded = db.load_user_profile()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get("custom_skills"), ["FastAPI", "Kubernetes"])
        self.assertIn("FastAPI", loaded.get("keywords", []))

        # Check raw SQLite column
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT custom_skills_json FROM user_profile WHERE id = 'default_user'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row[0])
        self.assertEqual(json.loads(row[0]), ["FastAPI", "Kubernetes"])

    def test_auto_detect_preserves_custom_skills(self):
        """Verifies auto_detect_alignment_from_resume preserves candidate custom skills."""
        resume = """
        Marcus Vance, Professional CDL-A Commercial Driver
        Credentials: CDL Class A with Tanker (N) and HazMat (X) Endorsements, Valid DOT Medical Card
        - Over 600,000 accident-free highway miles hauling regional refrigerated and dry van freight.
        """
        existing_skills = ["Snowflake", "dbt"]
        profile = career_compass.auto_detect_alignment_from_resume(
            resume,
            existing_custom_skills=existing_skills
        )
        self.assertEqual(profile.get("custom_skills"), ["Snowflake", "dbt"])
        self.assertIn("Snowflake", profile.get("keywords", []))
        self.assertIn("dbt", profile.get("keywords", []))

    def test_score_quiz_responses_preserves_custom_skills(self):
        """Verifies score_quiz_responses preserves candidate custom skills."""
        answers = {q["id"]: 0 for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS}
        existing_skills = ["Drone Piloting", "Thermal Imaging"]
        profile = career_compass.score_quiz_responses(
            answers,
            existing_custom_skills=existing_skills
        )
        self.assertEqual(profile.get("custom_skills"), ["Drone Piloting", "Thermal Imaging"])
        self.assertIn("Drone Piloting", profile.get("keywords", []))
        self.assertIn("Thermal Imaging", profile.get("keywords", []))

    def test_generate_adapted_prompt_with_custom_skills(self):
        """Verifies custom skills are explicitly incorporated into the adapted prompt evaluation rubric."""
        profile = {
            "primary_title": "Data Engineering",
            "archetype_title": "Cloud Data Architect",
            "compliance_gates": ["AWS Certified Solutions Architect"],
            "custom_skills": ["Apache Spark", "Delta Lake", "Trino"],
        }
        prompt = career_compass.generate_adapted_custom_prompt(profile)
        self.assertIn("Prioritized Candidate Skills & Tool Stack: Apache Spark, Delta Lake, Trino", prompt)


if __name__ == "__main__":
    unittest.main()
