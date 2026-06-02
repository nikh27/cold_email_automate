"""
email_templates.py — Personalized, human-sounding email generator.

5 different body templates × 5 subject lines = 25 unique combinations.
Templates rotate by contact ID so consecutive emails look different.
Role-based logic adjusts which template is used for executives vs recruiters.

Rules to sound human (NOT AI):
  - No "I hope this email finds you well"
  - No "I am writing to express my interest"
  - Use contractions (I'm, I've, I'd)
  - Mix sentence lengths — short punchy + medium
  - Use real numbers from Soumya's resume
  - Company name appears naturally, once
  - No bullet points in templates 0, 1, 2, 4
"""

import logging

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_first_name(full_name: str) -> str:
    """Extract first name. Fallback to 'there' if name is empty."""
    if not full_name or str(full_name).strip().lower() in ("none", ""):
        return "there"
    return str(full_name).strip().split()[0]


def classify_role(title: str) -> str:
    """
    Bucket the HR person's title into a broad category
    so we can pick the most appropriate email tone.
    """
    if not title:
        return "general"
    t = str(title).lower()

    if any(x in t for x in ["chief", "cpo", "president", "founder", "co-founder"]):
        return "executive"
    if any(x in t for x in ["vice president", "vp "]):
        return "vp"
    if any(x in t for x in ["talent acquisition", "recruiter", "ta ", "staffing"]):
        return "recruiter"
    if "director" in t:
        return "director"
    if "head" in t:
        return "head"
    return "general"


# ── Body Templates ───────────────────────────────────────────────────────────
# {first_name} and {company} are the only placeholders.
# Keep them feeling like a real person typed them.

_TEMPLATES = [

    # 0 — Direct & Confident  (good for: directors, heads)
    """\
Hi {first_name},

I'll keep this short. I'm a Computer Science grad (B.Tech, 8.1 CGPA) actively \
looking for a role in data science, ML, or software development — and {company} \
came up while I was researching companies worth reaching out to.

In the last couple of years I've shipped real things: a fraud detection model \
on 6.3 million financial transactions, a live multiplayer game built on Django \
WebSockets, and a recommendation engine I trained on 50,000+ ratings during my \
IBM internship. I also worked professionally at Shivam Informatics (full-stack) \
and TrialShoppy (backend), so I know how to contribute in a team, not just build \
things solo.

If there's an opening in data science, ML, or SDE that fits this background, \
I'd genuinely love to be considered. My resume is attached. Would it be okay \
to connect briefly?

Warm regards,
Soumya Kumari
+91 8969228544 | jhasoumya934@gmail.com\
""",

    # 1 — Value Focused  (good for: CPOs, VPs)
    """\
Hi {first_name},

I'm Soumya Kumari, a final-year B.Tech CSE student (8.1 CGPA, UIET MDU) \
writing to you because I think my profile could be a genuine fit for {company}.

Here's what I bring: hands-on ML and data science experience across real-world \
datasets — 6.3M+ transactions for fraud detection, 100K+ rows processed at \
IBM — along with full-stack Python and Django development skills. I've shipped \
working products, not just college assignments. I interned at IBM, worked \
professionally at two companies, and built projects that are still live today.

I'm open to roles across data science, ML engineering, or software development. \
Wherever I can learn fast and add value, I'll deliver. My resume is attached \
and I'd appreciate any consideration for suitable openings at your organization.

Thank you for your time,
Soumya Kumari
+91 8969228544 | jhasoumya934@gmail.com\
""",

    # 2 — Story-Based  (good for: talent acquisition, recruitment)
    """\
Hi {first_name},

I'm a Computer Science student finishing my B.Tech in 2026 (8.1 CGPA) who's \
spent the last two years building actual things — not just writing code for \
assignments.

A quick picture of what I've done: built a fraud detection pipeline on 6.3M+ \
transactions, shipped a real-time multiplayer web app using Django WebSockets \
(still live), trained a recommendation system on 50,000+ ratings at my IBM \
internship, and worked professionally at two companies contributing to \
production code. I'm comfortable with Python, SQL, TensorFlow, Scikit-learn, \
and Django end-to-end.

I'm looking for my next opportunity and {company} stood out. If you're hiring \
for data science, ML, or SDE roles — or if you'd simply like to keep my \
profile on file — I'd be grateful. Resume is attached.

Thank you,
Soumya Kumari
+91 8969228544 | jhasoumya934@gmail.com\
""",

    # 3 — Short & Punchy (good for: associate directors, managers)
    """\
Hi {first_name},

Quick intro — I'm Soumya Kumari, a 2026 B.Tech CSE fresher (8.1 CGPA) with \
solid experience in Python, machine learning, and full-stack development.

Some highlights:

• IBM AI/ML Intern — built a recommendation system on 50K+ movie ratings
• Fraud Detection — XGBoost pipeline on 6.3M+ transactions
• Live App — real-time multiplayer game via Django WebSockets (still running)
• Professional experience at Shivam Informatics and TrialShoppy

I'm actively looking for roles in data science, ML engineering, or software \
development at {company}. Available immediately, open to any location.

Resume attached. Happy to connect if there's a fit!

Soumya Kumari
+91 8969228544 | jhasoumya934@gmail.com\
""",

    # 4 — The Confident Fresher  (good for: general / unknown roles)
    """\
Hi {first_name},

I wanted to reach out to {company} directly. I've been researching companies \
where I think my background would be useful, and yours made the list.

I'm Soumya Kumari — a 2026 B.Tech CSE graduate (8.1 CGPA) with experience in \
machine learning, data science, and backend Python development. I've done an \
IBM AI/ML internship, worked professionally at two companies, and independently \
built a fraud detection system on 6.3M+ records and a real-time web app that's \
still live. I know Python, SQL, TensorFlow, Scikit-learn, OpenCV, and Django — \
and I'm comfortable working from raw data all the way to deployment.

I'm motivated, available immediately, and genuinely excited to contribute. If \
there's any opening that fits, I'd love to be considered. Resume is attached.

Looking forward to hearing from you,
Soumya Kumari
+91 8969228544 | jhasoumya934@gmail.com\
""",
]

# ── Subject Lines ────────────────────────────────────────────────────────────
# 5 variants, rotated separately from body templates.

_SUBJECTS = [
    "Data Science / ML Role — Soumya Kumari | B.Tech CSE, 8.1 CGPA",
    "Actively Seeking SDE / Data Scientist Role — Soumya Kumari (2026 Fresher)",
    "Soumya Kumari — Data Scientist & ML Engineer | Available Immediately",
    "ML & Data Science Profile — Soumya Kumari | IBM Internship + Live Projects",
    "Application for Data Science / SDE Role — Soumya Kumari | Fresh Graduate",
]


# ── Public aliases (for dashboard preview) ──────────────────────────────────
TEMPLATES = _TEMPLATES
SUBJECTS  = _SUBJECTS


# ── Public API ───────────────────────────────────────────────────────────────

def get_email_content(contact: dict) -> dict:
    """
    Generate personalized subject + body for one contact.
    Returns: {"subject": str, "body": str, "template_index": int}
    """
    first_name  = get_first_name(contact.get("name", ""))
    company     = contact.get("company") or "your organization"
    title       = contact.get("title") or ""
    contact_id  = contact.get("id", 0)

    # Base template selection (cycles through 0–4)
    template_idx = contact_id % len(_TEMPLATES)

    # Override for executives: avoid bullet-point template (3) & story (2)
    role = classify_role(title)
    if role in ("executive", "vp") and template_idx in (2, 3):
        template_idx = 1   # value-focused is best for C-suite

    body = _TEMPLATES[template_idx].format(
        first_name=first_name,
        company=company,
    )

    # Subject rotates independently (prime-step prevents alignment with body)
    subject_idx = (contact_id * 3 + template_idx) % len(_SUBJECTS)
    subject     = _SUBJECTS[subject_idx]

    return {
        "subject":        subject,
        "body":           body,
        "template_index": template_idx,
    }
