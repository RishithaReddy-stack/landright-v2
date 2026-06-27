"""
Deadline calculator — derives all important dates from source data.
Never stores computed dates; always calculates on demand.
"""
from datetime import datetime, timedelta
from typing import Optional

STEM_MAJORS = {
    "computer science", "cs", "data science", "electrical engineering",
    "mechanical engineering", "mathematics", "statistics", "physics",
    "information technology", "it", "software engineering", "bioinformatics",
    "chemical engineering", "civil engineering", "aerospace engineering",
}


def is_stem(major: Optional[str]) -> bool:
    if not major:
        return False
    return major.lower().strip() in STEM_MAJORS


def calculate_all(
    program_end_date: Optional[datetime],
    visa_type: Optional[str] = "F1",
    major: Optional[str] = None,
) -> dict:
    """
    Given program_end_date, return all relevant deadlines.
    Called by the agent tool — never stored in DB.
    """
    if not program_end_date:
        return {"error": "Program end date not set in your profile."}

    now = datetime.utcnow()
    stem = is_stem(major)

    # OPT application window: 90 days before → 60 days after graduation
    opt_earliest = program_end_date - timedelta(days=90)
    opt_latest   = program_end_date + timedelta(days=60)
    # OPT start date must be within 60 days of graduation
    opt_start_latest = program_end_date + timedelta(days=60)
    # OPT duration: 12 months standard, 36 months with STEM extension
    opt_end = program_end_date + timedelta(days=365)
    stem_extension_end = program_end_date + timedelta(days=365 * 3) if stem else None

    # Tax deadline: April 15 of the following calendar year
    tax_year = now.year if now.month < 4 else now.year
    tax_deadline = datetime(tax_year + 1, 4, 15)

    # SSN: eligible after 10 days of arrival + need work authorization
    # (calculated relative to now, assuming they just arrived)
    ssn_earliest = now + timedelta(days=10)

    days_to_graduation = (program_end_date - now).days

    result = {
        "program_end_date": program_end_date.strftime("%B %d, %Y"),
        "days_to_graduation": max(0, days_to_graduation),
        "visa_type": visa_type,
        "major": major,
        "is_stem": stem,
        "opt": {
            "apply_earliest": opt_earliest.strftime("%B %d, %Y"),
            "apply_latest": opt_latest.strftime("%B %d, %Y"),
            "start_latest": opt_start_latest.strftime("%B %d, %Y"),
            "end_date": opt_end.strftime("%B %d, %Y"),
            "duration_months": 12,
            "note": "Apply at least 3-4 months early — USCIS processing takes 3-5 months.",
        },
        "tax_deadline": tax_deadline.strftime("%B %d, %Y"),
        "ssn_earliest": ssn_earliest.strftime("%B %d, %Y"),
    }

    if stem and stem_extension_end:
        result["stem_extension"] = {
            "end_date": stem_extension_end.strftime("%B %d, %Y"),
            "duration_months": 36,
            "total_opt_months": 36,
            "note": f"{major} qualifies for 24-month STEM extension — 36 months total OPT.",
        }

    # Urgency flags
    result["urgent"] = []
    if 0 < days_to_graduation <= 90:
        result["urgent"].append(
            f"OPT application window opens NOW — graduation is in {days_to_graduation} days!"
        )
    if 0 < (tax_deadline - now).days <= 30:
        result["urgent"].append(
            f"Tax deadline is in {(tax_deadline - now).days} days!"
        )

    return result
