"""
Skippy - Built-in Sample Datasets & AI Connectivity Diagnostics
Provides realistic demo resumes and job descriptions for instant 1-click test drives,
plus real-time pre-flight AI connection testing.
"""

from typing import Tuple
import os

SAMPLE_RESUMES = {
    "Software & Cloud Engineer": """# Alex Mercer
**Email:** alex.mercer.dev@example.com | **Location:** Denver, CO | **Phone:** (303) 555-0192
**GitHub:** github.com/alexmercer-cloud | **LinkedIn:** linkedin.com/in/alexmercer-dev

## Professional Summary
Senior Cloud & Backend Engineer with 6+ years of experience designing, scaling, and automating distributed systems in AWS and GCP. Proven track record modernizing monolithic architectures into containerized microservices (Docker, Kubernetes) and building high-throughput REST/gRPC APIs in Python, Go, and TypeScript. Passionate about automated testing, infrastructure-as-code (Terraform), and robust CI/CD pipelines.

## Core Competencies & Technical Skills
- **Languages:** Python (FastAPI, Flask, Django), Go, TypeScript, SQL (PostgreSQL), Bash
- **Cloud & DevOps:** AWS (ECS, EKS, Lambda, S3, RDS), GCP, Terraform, Docker, Kubernetes, GitHub Actions
- **Data & Messaging:** Redis, Apache Kafka, PostgreSQL, DynamoDB
- **Practices:** Microservices, Distributed Systems, TDD, Agile/Scrum, Observability (Datadog, Prometheus)

## Professional Experience

### Senior Cloud Infrastructure Engineer — CloudScale Technologies (Remote)
*March 2022 – Present*
- Spearheaded migration of core billing API to containerized microservices on AWS EKS, reducing p99 latency by 42% and slashing cloud hosting costs by $180,000 annually.
- Designed and maintained Terraform modules managing multi-region cloud infrastructure across staging and production environments with zero downtime.
- Architected asynchronous event-driven notifications pipeline handling 15M+ events daily using Python, Kafka, and Redis caching.
- Mentored 5 mid-level engineers in distributed systems design, trunk-based development, and comprehensive unit/integration test patterns.

### Backend Software Engineer — Nexus Data Labs (Denver, CO)
*July 2019 – February 2022*
- Developed secure RESTful APIs in Python (FastAPI) and PostgreSQL serving 250,000+ active enterprise users.
- Automated end-to-end CI/CD testing pipelines with GitHub Actions, reducing deployment cycle times from 45 minutes to 8 minutes.
- Implemented role-based access control (RBAC) and OAuth2 authentication compliant with SOC 2 Type II audit standards.

## Education & Certifications
- **B.S. in Computer Science** — University of Colorado Boulder (2019)
- **AWS Certified Solutions Architect – Associate** (2023)
- **Certified Kubernetes Administrator (CKA)** (2024)
""",

    "Clinical Healthcare Specialist": """# Jordan Taylor, BSN, RN
**Email:** jordan.taylor.rn@example.com | **Location:** Chicago, IL | **Phone:** (312) 555-0144
**Licensure:** Illinois Registered Nurse (License #RN-041-992182, Active & Unencumbered)

## Professional Summary
Compassionate and clinically astute Registered Nurse with 7+ years of acute care, emergency department triage, and intensive care experience. Demonstrated excellence in patient assessment, critical care stabilization, medication administration, and interdisciplinary care coordination. Expert super-user in Epic Systems EHR and Cerner, with unwavering adherence to HIPAA privacy, infection control protocols, and patient-centered evidence-based care.

## Clinical Competencies & Certifications
- **Clinical Skills:** Acute Patient Triage, Hemodynamic Monitoring, IV/Vascular Access, Ventilator Management, Wound Care, Code Team Response
- **Informatics & Systems:** Epic EHR (Cadence, Willow, Stork), Cerner PowerChart, Pyxis MedStation, Omnicell
- **Certifications:**
  - Registered Nurse (RN) – Illinois State Board of Nursing
  - Basic Life Support (BLS) for Healthcare Providers (AHA)
  - Advanced Cardiovascular Life Support (ACLS) (AHA)
  - Pediatric Advanced Life Support (PALS) (AHA)
  - Trauma Nursing Core Course (TNCC)

## Professional Experience

### Clinical Staff Nurse (Emergency & Trauma Unit) — Northwestern Memorial Hospital (Chicago, IL)
*May 2021 – Present*
- Perform rapid, high-acuity triage and emergency nursing interventions for Level 1 trauma center handling 180+ patients daily.
- Administer emergency medications, titrated vasoactive infusions, and blood products with 100% medication safety verification rate.
- Serve as Epic EHR Clinical Super-User, training 24 incoming clinical staff on charting compliance, order entry, and rapid care documentation.
- Collaborate closely with trauma surgeons, emergency medicine physicians, and respiratory therapists during emergency resuscitations.

### Inpatient Acute Care Staff Nurse — Rush University Medical Center (Chicago, IL)
*August 2018 – April 2021*
- Delivered direct bedside nursing care for 5-6 acute medical-surgical and telemetry patients per shift with exemplary patient satisfaction ratings.
- Formulated individualized nursing care plans, executed post-surgical wound management, and coordinated multidisciplinary discharge planning.
- Awarded Daisy Award for Extraordinary Nursing Excellence (Q3 2020) for exceptional patient advocacy and clinical composure.

## Education
- **Bachelor of Science in Nursing (BSN)** — Loyola University Chicago, Magna Cum Laude (2018)
""",

    "Operations & Supply Chain Lead": """# Marcus Vance
**Email:** marcus.vance.ops@example.com | **Location:** Atlanta, GA | **Phone:** (404) 555-0177
**LinkedIn:** linkedin.com/in/marcusvance-ops

## Professional Summary
Results-driven Operations & Supply Chain Manager with 8+ years directing high-volume warehouse fulfillment, freight logistics, and global inventory procurement. Expert in lean manufacturing principles, ERP/WMS system integrations (SAP S/4HANA, Manhattan WMS), and end-to-end supply chain optimization. Proven track record reducing fulfillment cycle times by 35% while maintaining a 99.4% on-time delivery rate across multi-facility distribution networks.

## Core Competencies
- **Supply Chain & Logistics:** Multi-Site Fulfillment, Freight Logistics (FTL/LTL/Intermodal), Route Optimization, Carrier Contract Negotiation
- **Inventory & Operations:** Demand Forecasting, Lean Six Sigma, Safety Compliance (OSHA), Vendor Scorecarding, CAPEX Budgeting
- **Systems & Technology:** SAP S/4HANA, Manhattan WMS, Oracle NetSuite, Tableau, SQL, Advanced Excel (VBA/PowerQuery)

## Professional Experience

### Senior Distribution & Operations Manager — Apex Logistics Hub (Atlanta, GA)
*January 2021 – Present*
- Lead operations for a 450,000 sq. ft. automated fulfillment distribution center managing 120+ team members and $65M in annual inventory.
- Reduced shipping dock turnaround times by 28% and cut freight shrinkage to under 0.05% through automated barcode scanning and audit gates.
- Spearheaded transition from legacy warehouse software to Manhattan Associates WMS, achieving on-time launch under budget.
- Championed comprehensive OSHA safety overhaul, achieving 620 consecutive accident-free operational days.

### Supply Chain & Inventory Analyst — Meridian Global Products (Savannah, GA)
*June 2017 – December 2020*
- Modeled seasonal demand forecasts for 1,200+ active SKUs across 4 regional hubs, boosting inventory turnover by 18%.
- Negotiated vendor freight tariffs with international ocean and domestic motor carriers, driving $420,000 in annual cost savings.
- Built interactive Tableau KPI dashboards tracking order accuracy, lead times, and transit exceptions for executive leadership.

## Education & Credentials
- **B.B.A. in Supply Chain Management** — Georgia Institute of Technology (2017)
- **APICS Certified Supply Chain Professional (CSCP)** (2021)
- **Lean Six Sigma Green Belt (SSGB)** (2020)
""",

    "Skilled Trades & Automation Technician": """# Robert 'Bob' Kowalski
**Email:** bob.kowalski.hvac@example.com | **Location:** Columbus, OH | **Phone:** (614) 555-0188
**Licensure:** State of Ohio Licensed HVAC Contractor (#HVAC-48210) | EPA Universal Section 608 Certified

## Professional Summary
Master HVAC/R and Industrial Automation Technician with 10+ years of hands-on experience diagnosing, installing, and servicing commercial refrigeration, hydronic systems, and automated Building Management Systems (BMS). Deep mechanical and electrical expertise across high-tonnage chillers, VRF heat pumps, three-phase electrical circuitry, and PLC diagnostics. Committed to zero-incident jobsite safety, precision troubleshooting, and energy efficiency compliance.

## Technical Skills & Certifications
- **Trade Competencies:** Commercial HVAC/R, Chillers, Boilers, VRV/VRF Systems, Ammonia Refrigeration, Brazing/Soldering, Duct Fabrication
- **Controls & Electrical:** Three-Phase 480V/208V Power, Ladder Logic, Honeywell/Johnson Controls BMS, PLC Diagnostics, Motor Controls
- **Certifications & Licenses:**
  - Ohio State Licensed HVAC Contractor (#HVAC-48210)
  - EPA Section 608 Universal Certification (Freon / Clean Air Act)
  - OSHA 30-Hour Construction Safety Certification
  - NATE Certified (Commercial Refrigeration & Heat Pumps)

## Work History

### Lead Commercial HVAC/R & Controls Specialist — Buckeye Climate Solutions (Columbus, OH)
*April 2019 – Present*
- Direct commercial HVAC installation and emergency service contracts for hospitals, cold storage warehouses, and university campuses.
- Commission and calibrate complex BMS systems (Johnson Controls Metasys and Honeywell WEBs), optimizing client energy use by up to 22%.
- Lead preventive maintenance contracts on 100+ ton centrifugal chillers, industrial compressors, and walk-in freezer cooling plants.
- Train 8 apprentice and journeyman technicians on schematic interpretation, evacuation, nitrogen pressure testing, and refrigerant recovery.

### Commercial HVAC Service Technician — Tri-State Mechanical Services (Dayton, OH)
*August 2014 – March 2019*
- Performed rapid-response electrical and mechanical troubleshooting on commercial rooftop units (RTUs), heat exchangers, and air handlers.
- Successfully recovered and recharged thousands of pounds of commercial refrigerants in strict adherence with EPA Section 608 guidelines.
- Received 2018 Technician of the Year Award for maintaining highest first-time fix rate (94.2%) across the regional fleet.

## Education & Apprenticeship
- **Associate of Applied Science in Heating, Ventilating & Air Conditioning** — Columbus State Community College (2014)
- **4-Year Certified Plumbing & HVAC Apprenticeship Program** — Completed with Honors
"""
}

SAMPLE_JOBS = [
    {
        "title": "Cloud Platform & DevOps Engineer",
        "company": "Apex Cloud Systems",
        "location": "Remote (US)",
        "workplace_type": "Remote",
        "text": """Apex Cloud Systems is looking for a Senior Cloud Platform & DevOps Engineer to join our distributed infrastructure team.

About the Role:
You will be responsible for scaling, securing, and maintaining our multi-region AWS cloud platform. You will work closely with backend engineering teams to build automated CI/CD deployment pipelines, manage Kubernetes clusters, and write clean Infrastructure-as-Code.

Key Responsibilities:
- Manage, monitor, and optimize production AWS infrastructure using Terraform and CloudFormation.
- Maintain and enhance production Kubernetes (EKS) clusters hosting containerized microservices.
- Design resilient CI/CD pipelines (GitHub Actions) for automated testing, linting, and zero-downtime deployment.
- Implement robust telemetry, alerting, and logging with Prometheus, Grafana, and Datadog.
- Participate in an on-call rotation with dedicated post-incident blameless reviews.

Requirements:
- 4+ years of professional experience in cloud engineering, DevOps, or backend infrastructure.
- Demonstrated hands-on proficiency with AWS, Terraform, Docker, and Kubernetes.
- Solid programming/scripting abilities in Python, Go, or Bash.
- Deep familiarity with Linux system administration, networking protocols (TCP/IP, DNS, TLS), and RESTful APIs.
- Strong collaborative mindset and clear written/verbal communication skills."""
    },
    {
        "title": "Emergency Department Registered Nurse (Staff Nurse II)",
        "company": "Metro Health Hospital",
        "location": "Chicago, IL",
        "workplace_type": "On-site",
        "text": """Metro Health Hospital is seeking an experienced, dedicated Registered Nurse (RN) to join our fast-paced Emergency Department team.

Position Overview:
The Emergency Department Staff Nurse provides direct patient care, triage assessment, and clinical stabilization for pediatric, adult, and geriatric patients presenting with acute illnesses and injuries in a busy metropolitan hospital.

Key Duties:
- Conduct rapid patient triage using the Emergency Severity Index (ESI) protocol.
- Initiate emergency life-saving nursing interventions, administer prescribed medications, and start intravenous access lines.
- Monitor patient hemodynamics, electrocardiograms, and post-procedural recovery.
- Chart all assessments, medication administrations, and provider orders accurately in Epic EHR.
- Educate patients and family members on discharge instructions, medication schedules, and outpatient follow-up.

Requirements:
- Valid, unencumbered Registered Nurse (RN) license in the State of Illinois.
- 2+ years of acute care or emergency department nursing experience.
- Current BLS (Basic Life Support) and ACLS (Advanced Cardiovascular Life Support) certifications from the American Heart Association.
- Proficiency with electronic health record (EHR) platforms (Epic Systems strongly preferred).
- Ability to thrive in a high-urgency, collaborative clinical environment."""
    },
    {
        "title": "Operations & Logistics Hub Supervisor",
        "company": "FastTrack Distribution",
        "location": "Atlanta, GA",
        "workplace_type": "On-site",
        "text": """FastTrack Distribution is looking for an energetic Operations & Logistics Hub Supervisor to oversee daily fulfillment and outbound freight operations at our regional Atlanta logistics center.

Key Responsibilities:
- Supervise a team of 30+ warehouse associates across receiving, pick-and-pack, sorting, and loading bays.
- Coordinate outbound linehaul freight with regional carriers (FTL/LTL) to ensure 99%+ on-time departure.
- Monitor inventory accuracy, scan compliance, and cycle counts using our Warehouse Management System (WMS).
- Enforce strict jobsite safety standards and OSHA compliance across the dock floor.
- Identify bottleneck delays and streamline warehouse workflows to optimize throughput.

Requirements:
- 3+ years of experience in warehouse operations, distribution, or freight logistics.
- Working experience with modern WMS software (Manhattan, SAP, or similar) and RF scanning technology.
- Demonstrated leadership ability to motivate, coach, and organize cross-functional shift teams.
- Strong organizational, problem-solving, and communication skills.
- High School Diploma or equivalent (Bachelor's degree in Logistics or Supply Chain is a plus)."""
    }
]


def test_ai_connection(
    model_choice: str,
    api_key: str,
    local_base_url: str = "",
    local_model_name: str = ""
) -> Tuple[bool, str]:
    """
    Performs a lightweight, non-destructive connection test to the selected AI provider.
    Returns (True, success_message) or (False, error_message).
    """
    clean_key = (api_key or "").strip()
    is_local = "Local" in (model_choice or "")

    if not is_local and not clean_key:
        return False, "Please provide an API key before testing the connection."

    try:
        from evaluator import resolve_model_id, _get_completion

        target_model = resolve_model_id(
            model_choice=model_choice,
            local_model_name=local_model_name,
            model_override=""
        )

        completion_fn = _get_completion()

        kwargs = {
            "model": target_model,
            "messages": [
                {"role": "user", "content": "Ping. Reply with: OK"}
            ],
            "max_tokens": 10,
            "timeout": 12,
        }

        if is_local:
            if local_base_url:
                kwargs["api_base"] = local_base_url.rstrip("/")
            if clean_key:
                kwargs["api_key"] = clean_key
        else:
            kwargs["api_key"] = clean_key

        response = completion_fn(**kwargs)
        if response and response.choices:
            return True, f"Connection verified successfully! Connected to {target_model}."
        return True, "Connection verified successfully!"

    except Exception as exc:
        err_str = str(exc)
        # Friendly translations of common provider errors
        if "API_KEY_INVALID" in err_str or "401" in err_str or "invalid_api_key" in err_str:
            return False, "Invalid API key. Please check your key from the provider dashboard."
        if "ConnectionRefused" in err_str or "Failed to establish a new connection" in err_str:
            return False, f"Could not connect to {local_base_url or 'localhost'}. Is your local model server running?"
        if "rate_limit" in err_str.lower() or "429" in err_str:
            return False, "Rate limit reached on provider. Please wait a moment and try again."
        return False, f"Connection failed: {err_str[:160]}"
