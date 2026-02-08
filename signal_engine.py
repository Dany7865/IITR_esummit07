"""
Procurement Signal "Fingerprinting" – Knowledge-Graph style mapping.
Maps industry events/signals to HPCL product categories with reasoning.
E.g. "Expansion" -> High demand for Bitumen (paving) and Industrial Fuels (boilers).
"""
from typing import List, Dict, Any

# Event/signal -> (HPCL products, reasoning)
SIGNAL_GRAPH = {
    "expansion": {
        "products": ["Bitumen", "Industrial Fuels", "Furnace Oil"],
        "reasoning": "Expansion = new construction (paving, bitumen) and increased boiler/furnace load (industrial fuels).",
    },
    "new plant": {
        "products": ["Industrial Fuels", "Furnace Oil", "Petcoke"],
        "reasoning": "New plant typically requires captive power and process fuel (Furnace Oil, Petcoke for cement/steel).",
    },
    "tender": {
        "products": ["Industrial Fuels", "Bitumen", "Marine Fuel"],
        "reasoning": "Tender indicates active procurement; product mix depends on industry (inferred from text).",
    },
    "marine": {
        "products": ["Marine Fuel", "LSHS", "Bunker"],
        "reasoning": "Marine/shipping segment requires bunker fuel and marine-grade LSHS per IMO specs.",
    },
    "shipping": {
        "products": ["Marine Fuel", "Bunker"],
        "reasoning": "Shipping and vessel operations use marine fuels and bunkering.",
    },
    "road": {
        "products": ["Bitumen", "VGB", "Paving Grade"],
        "reasoning": "Road/highway projects use bitumen (VG-30, VG-40) for paving and overlay.",
    },
    "highway": {
        "products": ["Bitumen", "VGB", "Paving Grade"],
        "reasoning": "Highway construction requires paving-grade bitumen (VG-30 typical for highways).",
    },
    "cement": {
        "products": ["Petcoke", "Furnace Oil", "Industrial Fuels"],
        "reasoning": "Cement industry uses Petcoke and furnace oil for kiln and grinding.",
    },
    "construction": {
        "products": ["Bitumen", "Industrial Fuels", "Furnace Oil"],
        "reasoning": "Construction sector needs bitumen (roads/sites) and fuels for equipment and temporary power.",
    },
    "power": {
        "products": ["Furnace Oil", "LSHS", "Industrial Fuels"],
        "reasoning": "Power generation and DG sets use furnace oil and LSHS.",
    },
    "refinery": {
        "products": ["Specialty Products", "Lubes", "Feedstocks"],
        "reasoning": "Refinery/petrochemical segment uses specialty products and feedstocks.",
    },
    "aviation": {
        "products": ["ATF", "Jet Fuel"],
        "reasoning": "Aviation segment requires ATF and jet fuel to spec.",
    },
}


def fingerprint_signals(raw_text: str) -> List[Dict[str, Any]]:
    """
    Build a "Signal Fingerprint": which events/signals were detected and
    which HPCL products they map to, with reasoning.
    """
    text = (raw_text or "").lower()
    seen_products = set()
    out = []
    for signal, data in SIGNAL_GRAPH.items():
        if signal not in text:
            continue
        products = data.get("products", [])
        reasoning = data.get("reasoning", "")
        # Dedupe by product set
        key = tuple(sorted(products))
        if key in seen_products:
            continue
        seen_products.add(key)
        out.append({
            "event": signal,
            "products": products,
            "reasoning": reasoning,
        })
    return out[:10]  # cap for UI


def get_primary_product_reasoning(industry: str, products: List[str]) -> str:
    """One-line reasoning for the primary recommended product (for dossier)."""
    if not products:
        return "General industrial fuels opportunity."
    p = products[0]
    if "Bitumen" in p or "VGB" in p:
        return "Highway/road and paving projects drive Bitumen (VG-30/VG-40) demand. HPCL supplies to NHAI and state highways."
    if "Marine" in p or "Bunker" in p:
        return "Marine/shipping segment requires compliant bunker fuel. HPCL offers marine fuels at key Indian ports."
    if "Petcoke" in p or "Furnace" in p:
        return "Cement/industrial expansion increases demand for Petcoke and Furnace Oil for kilns and boilers."
    if "ATF" in p or "Jet" in p:
        return "Aviation segment requires ATF to spec. HPCL supplies major airports."
    return f"Industrial demand signals align with {p}. HPCL has supply and logistics capability."
