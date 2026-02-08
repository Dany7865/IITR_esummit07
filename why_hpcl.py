"""
"Why HPCL?" – Lead Dossier competitive intelligence / battlecard.
Auto-generated comparison of HPCL product specs vs industry standards for the relevant segment.
"""
from typing import List, Dict, Any

# Per-product category: Why HPCL (specs vs standards, differentiators)
WHY_HPCL_BATTLECARDS = {
    "Marine Fuel": {
        "headline": "HPCL Marine Fuels vs industry",
        "points": [
            "HPCL supplies IMO 2020-compliant low-sulphur marine fuels at major Indian ports (Mumbai, Kochi, Chennai, Vizag).",
            "Quality conforms to ISO 8217; consistent supply for bunkering and long-term contracts.",
            "Strong logistics and storage at port locations reduces delivery risk for shipping lines.",
        ],
        "cta": "Position HPCL’s port infrastructure and compliance for marine tenders.",
    },
    "Bitumen": {
        "headline": "HPCL Bitumen for roads and paving",
        "points": [
            "VG-30 and VG-40 grades supplied to NHAI and state highway projects; proven track record.",
            "Meets IS 73 and MORTH specs; suitable for hot-mix and paving applications.",
            "Pan-India supply chain supports timely delivery for project schedules.",
        ],
        "cta": "Lead with NHAI/state project references and VG-30 availability for highway tenders.",
    },
    "Petcoke": {
        "headline": "HPCL Petcoke for cement and industrial",
        "points": [
            "Petcoke suitable for cement kilns and industrial furnaces; quality specs as per offtake requirements.",
            "Sourcing from HPCL refineries ensures consistent quality and supply security.",
            "Competitive pricing and volume flexibility for large cement/steel customers.",
        ],
        "cta": "Emphasise refinery-backed supply and quality consistency for expansion/new plant discussions.",
    },
    "Furnace Oil": {
        "headline": "HPCL Furnace Oil and industrial fuels",
        "points": [
            "Furnace oil and LSHS for boilers, kilns, and process heating; meets industrial specs.",
            "Reliable supply from HPCL refineries; supports both spot and contract requirements.",
            "Technical support available for combustion and efficiency optimisation.",
        ],
        "cta": "Offer furnace oil/LSHS for expansion and captive power needs.",
    },
    "Industrial Fuels": {
        "headline": "HPCL Industrial Fuels",
        "points": [
            "Wide range of industrial fuels for manufacturing, power backup, and process use.",
            "Supply chain and safety standards aligned with large industrial customers.",
            "Flexible delivery and contract options for bulk offtake.",
        ],
        "cta": "Position full product range and logistics for multi-site industrials.",
    },
    "ATF": {
        "headline": "HPCL ATF and jet fuel",
        "points": [
            "ATF supplied to major airports; meets DGCA and international specs.",
            "Into-plane and storage infrastructure at key airports.",
            "Quality and compliance documentation for aviation tenders.",
        ],
        "cta": "Lead with airport presence and compliance for aviation contracts.",
    },
    "LSHS": {
        "headline": "HPCL LSHS",
        "points": [
            "Low-sulphur heavy stock for industrial boilers and marine applications.",
            "Meets environmental norms; suitable for long-term supply agreements.",
            "Available at select locations; discuss logistics for your geography.",
        ],
        "cta": "Position LSHS for boiler and marine segments with compliance focus.",
    },
    "Bunker": {
        "headline": "HPCL Bunker fuels",
        "points": [
            "Bunker fuels at key ports; IMO 2020 compliant options.",
            "Competitive pricing and reliable supply for shipping lines.",
            "Coordination with port authorities for smooth bunkering.",
        ],
        "cta": "Use port coverage and compliance as differentiators in marine tenders.",
    },
    "VGB": {
        "headline": "HPCL VGB (Viscosity Grade Bitumen)",
        "points": [
            "VGB grades for specialised paving and industrial applications.",
            "Consistent quality from refinery production.",
            "Suitable for state and private road projects.",
        ],
        "cta": "Recommend VGB where spec requires viscosity-grade bitumen.",
    },
    "Paving Grade": {
        "headline": "HPCL Paving-grade bitumen",
        "points": [
            "Paving-grade bitumen (VG-10, VG-30, VG-40) for roads and runways.",
            "Widely used in NHAI and state projects.",
            "Supply and logistics aligned to project timelines.",
        ],
        "cta": "Lead with VG-30 for highway projects and project references.",
    },
    "Specialty Products": {
        "headline": "HPCL Specialty products",
        "points": [
            "Specialty and value-added products for refinery and petrochemical offtake.",
            "Quality and specs as per customer and application.",
            "Technical engagement for custom requirements.",
        ],
        "cta": "Position specialty range for refinery/petrochemical tenders.",
    },
}


def build_why_hpcl(products: List[str], industry: str) -> Dict[str, Any]:
    """
    Build "Why HPCL?" section for the lead dossier (battlecard).
    Returns headline, points, and CTA for the primary product; plus list of all relevant battlecards.
    """
    if not products:
        product = "Industrial Fuels"
    else:
        product = products[0]
    card = WHY_HPCL_BATTLECARDS.get(product) or WHY_HPCL_BATTLECARDS.get("Industrial Fuels", {})
    all_cards = []
    for p in products[:5]:
        c = WHY_HPCL_BATTLECARDS.get(p)
        if c and c not in all_cards:
            all_cards.append({"product": p, **c})
    return {
        "primary_headline": card.get("headline", "Why HPCL"),
        "primary_points": card.get("points", []),
        "primary_cta": card.get("cta", "Reach out with product sheet and capability note."),
        "all_battlecards": all_cards or [{"product": product, **card}],
    }


def sales_pitch_script(company: str, industry: str, products: List[str], summary: str) -> str:
    """Pre-filled sales pitch script for the lead (for mobile/dossier)."""
    p = ", ".join(products[:3]) if products else "industrial fuels"
    return (
        f"Hi, I'm from HPCL Direct Sales. We noticed {company} may have requirements in {p} "
        f"({industry}). {summary[:150] if summary else 'We would like to discuss how HPCL can support your needs.'} "
        "We supply to leading players in the segment and would welcome a short conversation. "
        "Would you be open to a 15-minute call this week?"
    ).strip()
