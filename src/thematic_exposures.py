import re
from typing import Any


EXPOSURE_KEYS = [
    "ai",
    "data_center",
    "consumer",
    "automotive",
    "industrial",
    "china",
    "memory",
    "foundry",
    "equipment",
    "optical",
    "energy",
]

DB_EXPOSURE_COLUMNS = {
    "ai": "ai_exposure_score",
    "data_center": "data_center_exposure_score",
    "consumer": "consumer_exposure_score",
    "automotive": "automotive_exposure_score",
    "industrial": "industrial_exposure_score",
    "china": "china_exposure_score",
    "memory": "memory_cycle_exposure_score",
    "foundry": "foundry_exposure_score",
    "equipment": "equipment_cycle_exposure_score",
    "optical": "optical_networking_exposure_score",
}

SEMICONDUCTOR_SUBCATEGORY = {
    "AAOI": "optical_networking",
    "ADI": "analog_mixed_signal",
    "AEHR": "test_equipment",
    "AEIS": "equipment_power",
    "AEVA": "lidar_sensor",
    "AIRG": "rf_wireless",
    "ALAB": "optical_networking",
    "ALGM": "power_sensing",
    "AMBA": "ai_vision_processor",
    "AMD": "cpu_gpu_processor",
    "AOSL": "power_mosfet",
    "AVGO": "networking_custom_silicon",
    "COHR": "optical_networking",
    "COHU": "test_equipment",
    "CRUS": "audio_mixed_signal",
    "DIOD": "discrete_analog",
    "FORM": "test_equipment",
    "GSIT": "memory_mram",
    "HIMX": "display_driver",
    "INDI": "automotive_radar",
    "INTC": "cpu_foundry_processor",
    "IPGP": "industrial_photonics",
    "IPWR": "power_management",
    "KLAC": "process_control_equipment",
    "LASR": "laser_photonics",
    "LFUS": "power_discrete",
    "LRCX": "wafer_fab_equipment",
    "LSCC": "fpga_programmable",
    "MCHP": "mcu_analog",
    "MCHPP": "mcu_analog",
    "MOBX": "rf_wireless",
    "MPWR": "power_management",
    "MRAM": "memory_mram",
    "MRVL": "networking_custom_silicon",
    "MTSI": "rf_photonics",
    "MU": "memory",
    "MXL": "data_infrastructure",
    "NVDA": "ai_gpu_accelerator",
    "NVEC": "spintronics_sensor",
    "NVTS": "power_gan",
    "NXPI": "automotive_industrial",
    "ON": "power_analog",
    "PI": "rfid_iot",
    "PLAB": "photomask_equipment",
    "POWI": "power_management",
    "PRSO": "rf_wireless",
    "PXLW": "display_driver",
    "QCOM": "rf_wireless_mobile",
    "QRVO": "rf_wireless",
    "QUIK": "fpga_iot",
    "RMBS": "memory_interface_ip",
    "SIMO": "storage_controller",
    "SITM": "networking_timing",
    "SLAB": "iot_mixed_signal",
    "SMCI": "ai_server",
    "SMTC": "analog_mixed_signal",
    "SWKS": "rf_wireless",
    "SYNA": "human_interface",
    "TER": "test_equipment",
    "TXN": "analog_embedded",
}

BASE_CATEGORY_SCORES = {
    "assembly": {"foundry": 0.55, "equipment": 0.15, "consumer": 0.35, "automotive": 0.25},
    "device": {"consumer": 0.45, "industrial": 0.35, "ai": 0.15},
    "energy": {"energy": 0.95, "industrial": 0.45, "data_center": 0.25, "consumer": 0.25},
    "equipment": {"equipment": 0.92, "foundry": 0.65, "memory": 0.45, "ai": 0.45},
    "foundry": {"foundry": 0.95, "ai": 0.65, "data_center": 0.55, "consumer": 0.45, "automotive": 0.35, "china": 0.35},
    "ip": {"ai": 0.45, "data_center": 0.55, "consumer": 0.35, "automotive": 0.25},
    "memory": {"memory": 0.95, "ai": 0.65, "data_center": 0.65, "consumer": 0.30},
    "semiconductor": {"ai": 0.25, "data_center": 0.25, "consumer": 0.25, "automotive": 0.25, "industrial": 0.25},
    "server": {"ai": 0.85, "data_center": 0.95, "memory": 0.25, "energy": 0.25},
}

SUBCATEGORY_SCORES = {
    "ai_gpu_accelerator": {"ai": 0.98, "data_center": 0.95, "memory": 0.45, "foundry": 0.45, "consumer": 0.25, "automotive": 0.35, "china": 0.35},
    "ai_server": {"ai": 0.85, "data_center": 0.95, "memory": 0.35, "energy": 0.35},
    "ai_vision_processor": {"ai": 0.80, "automotive": 0.65, "consumer": 0.45, "industrial": 0.30},
    "analog_embedded": {"industrial": 0.85, "automotive": 0.70, "consumer": 0.30},
    "analog_mixed_signal": {"industrial": 0.75, "automotive": 0.60, "consumer": 0.35},
    "audio_mixed_signal": {"consumer": 0.85, "automotive": 0.25},
    "automotive_industrial": {"automotive": 0.90, "industrial": 0.70, "consumer": 0.25},
    "automotive_radar": {"automotive": 0.92, "industrial": 0.45, "ai": 0.35},
    "cpu_foundry_processor": {"data_center": 0.82, "foundry": 0.85, "ai": 0.50, "consumer": 0.45, "industrial": 0.35, "china": 0.30},
    "cpu_gpu_processor": {"ai": 0.78, "data_center": 0.86, "consumer": 0.55, "foundry": 0.45, "china": 0.30},
    "data_infrastructure": {"data_center": 0.82, "ai": 0.45, "industrial": 0.25},
    "discrete_analog": {"industrial": 0.70, "automotive": 0.65, "consumer": 0.25},
    "display_driver": {"consumer": 0.85, "automotive": 0.25},
    "equipment_power": {"equipment": 0.80, "foundry": 0.55, "memory": 0.35, "industrial": 0.35},
    "fpga_iot": {"industrial": 0.75, "ai": 0.35, "data_center": 0.35, "automotive": 0.25},
    "fpga_programmable": {"industrial": 0.80, "data_center": 0.55, "ai": 0.45, "automotive": 0.35},
    "human_interface": {"consumer": 0.88, "automotive": 0.30},
    "industrial_photonics": {"industrial": 0.85, "optical": 0.45, "equipment": 0.25},
    "iot_mixed_signal": {"industrial": 0.65, "consumer": 0.45, "automotive": 0.35},
    "laser_photonics": {"optical": 0.70, "industrial": 0.55, "equipment": 0.30},
    "lidar_sensor": {"automotive": 0.75, "industrial": 0.35, "ai": 0.25},
    "mcu_analog": {"automotive": 0.72, "industrial": 0.75, "consumer": 0.35},
    "memory_interface_ip": {"memory": 0.82, "data_center": 0.72, "ai": 0.45},
    "memory_mram": {"memory": 0.85, "industrial": 0.45, "ai": 0.30},
    "networking_custom_silicon": {"data_center": 0.88, "ai": 0.65, "optical": 0.35, "consumer": 0.20},
    "networking_timing": {"data_center": 0.70, "industrial": 0.50, "optical": 0.35},
    "optical_networking": {"optical": 0.92, "data_center": 0.82, "ai": 0.45},
    "photomask_equipment": {"equipment": 0.75, "foundry": 0.65, "memory": 0.40},
    "power_analog": {"automotive": 0.78, "industrial": 0.70, "energy": 0.30, "consumer": 0.25},
    "power_discrete": {"industrial": 0.70, "automotive": 0.65, "energy": 0.35},
    "power_gan": {"energy": 0.55, "data_center": 0.40, "automotive": 0.45, "industrial": 0.50},
    "power_management": {"industrial": 0.70, "automotive": 0.55, "data_center": 0.35, "energy": 0.30, "consumer": 0.25},
    "power_mosfet": {"automotive": 0.75, "industrial": 0.70, "energy": 0.35, "consumer": 0.25},
    "power_sensing": {"automotive": 0.78, "industrial": 0.65, "energy": 0.25},
    "process_control_equipment": {"equipment": 0.95, "foundry": 0.70, "memory": 0.50, "ai": 0.45},
    "rf_photonics": {"consumer": 0.45, "automotive": 0.25, "optical": 0.55, "data_center": 0.35},
    "rf_wireless": {"consumer": 0.78, "automotive": 0.25, "industrial": 0.25},
    "rf_wireless_mobile": {"consumer": 0.80, "automotive": 0.45, "ai": 0.40, "data_center": 0.25},
    "rfid_iot": {"industrial": 0.65, "consumer": 0.35},
    "spintronics_sensor": {"industrial": 0.55, "automotive": 0.40, "memory": 0.35},
    "storage_controller": {"memory": 0.70, "consumer": 0.45, "data_center": 0.35},
    "test_equipment": {"equipment": 0.85, "foundry": 0.45, "memory": 0.40, "ai": 0.35},
    "wafer_fab_equipment": {"equipment": 0.95, "foundry": 0.75, "memory": 0.55, "ai": 0.45},
}

TICKER_OVERRIDES = {
    "ASML": {"equipment": 0.98, "foundry": 0.85, "memory": 0.55, "ai": 0.55, "china": 0.45},
    "AMAT": {"equipment": 0.95, "foundry": 0.75, "memory": 0.55, "ai": 0.50, "china": 0.35},
    "LRCX": {"equipment": 0.95, "foundry": 0.70, "memory": 0.70, "ai": 0.45, "china": 0.35},
    "KLAC": {"equipment": 0.95, "foundry": 0.75, "memory": 0.50, "ai": 0.45, "china": 0.35},
    "TSM": {"foundry": 0.98, "ai": 0.85, "data_center": 0.80, "consumer": 0.55, "automotive": 0.45, "china": 0.70},
    "GFS": {"foundry": 0.90, "automotive": 0.45, "industrial": 0.45, "data_center": 0.35, "china": 0.10},
    "TSEM": {"foundry": 0.82, "industrial": 0.50, "automotive": 0.40, "consumer": 0.35},
    "ARM": {"ai": 0.78, "data_center": 0.72, "consumer": 0.65, "automotive": 0.45},
    "CEVA": {"consumer": 0.60, "ai": 0.45, "automotive": 0.35, "industrial": 0.30},
    "AIP": {"data_center": 0.55, "ai": 0.45, "automotive": 0.25, "industrial": 0.25},
    "RMBS": {"memory": 0.85, "data_center": 0.75, "ai": 0.45},
    "FSLR": {"energy": 0.98, "industrial": 0.45, "china": 0.20},
    "RUN": {"energy": 0.95, "consumer": 0.65, "industrial": 0.25},
    "PLUG": {"energy": 0.95, "industrial": 0.65, "data_center": 0.20},
    "CSIQ": {"energy": 0.95, "consumer": 0.35, "industrial": 0.45, "china": 0.35},
    "SHLS": {"energy": 0.90, "industrial": 0.55},
    "ASTI": {"energy": 0.90, "consumer": 0.35, "industrial": 0.35},
    "TYGO": {"energy": 0.90, "consumer": 0.40, "industrial": 0.40},
}

KEYWORD_BONUSES = {
    "ai": ["ai", "artificial intelligence", "accelerator", "gpu", "machine learning"],
    "data_center": ["data center", "datacenter", "server", "cloud", "hyperscale", "networking"],
    "consumer": ["consumer", "mobile", "smartphone", "pc", "gaming", "display", "audio"],
    "automotive": ["automotive", "vehicle", "ev", "adas", "lidar", "radar"],
    "industrial": ["industrial", "factory", "automation", "iot", "embedded"],
    "china": ["china", "taiwan", "export control", "export controls"],
    "memory": ["memory", "dram", "nand", "hbm", "sram"],
    "foundry": ["foundry", "fab", "wafer", "process node", "tsmc"],
    "equipment": ["equipment", "lithography", "etch", "deposition", "metrology", "inspection"],
    "optical": ["optical", "photonics", "transceiver", "silicon photonics"],
    "energy": ["energy", "solar", "grid", "hydrogen", "battery", "power conversion"],
}


def _empty_scores() -> dict[str, float]:
    return {key: 0.0 for key in EXPOSURE_KEYS}


def _merge_max(scores: dict[str, float], updates: dict[str, float]) -> None:
    for key, value in updates.items():
        if key in scores:
            scores[key] = max(scores[key], float(value))


def _clamp_scores(scores: dict[str, float]) -> dict[str, float]:
    return {key: max(0.0, min(1.0, round(float(value), 3))) for key, value in scores.items()}


def normalize_text(*values: Any) -> str:
    return re.sub(r"\s+", " ", " ".join(str(v or "") for v in values).lower()).strip()


def derive_semiconductor_category(ticker: str, existing_category: str | None) -> str:
    category = (existing_category or "other").strip() or "other"
    if category == "semiconductor" and ticker.upper() in SEMICONDUCTOR_SUBCATEGORY:
        return SEMICONDUCTOR_SUBCATEGORY[ticker.upper()]
    return category


def get_business_role(category: str) -> str:
    if category in {"foundry", "memory", "semiconductor"} or category in SUBCATEGORY_SCORES:
        return "chip_maker"
    if category == "equipment":
        return "equipment_supplier"
    if category == "ip":
        return "ip_licensor"
    if category == "assembly":
        return "osat_ems"
    if category == "server":
        return "system_integrator"
    if category == "device":
        return "device_maker"
    if category == "energy":
        return "energy_grid"
    return "other"


def score_ticker_exposures(
    ticker: str,
    category: str | None,
    company_name: str | None = "",
    description: str | None = "",
    products: str | None = "",
    markets: str | None = "",
    themes: str | None = "",
    sentiment: dict[str, Any] | None = None,
) -> dict[str, float]:
    ticker = ticker.upper()
    derived_category = derive_semiconductor_category(ticker, category)
    scores = _empty_scores()

    _merge_max(scores, BASE_CATEGORY_SCORES.get(category or "", {}))
    _merge_max(scores, BASE_CATEGORY_SCORES.get(derived_category, {}))
    _merge_max(scores, SUBCATEGORY_SCORES.get(derived_category, {}))
    _merge_max(scores, TICKER_OVERRIDES.get(ticker, {}))

    text = normalize_text(company_name, description, products, markets, themes)
    for key, keywords in KEYWORD_BONUSES.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits:
            scores[key] = max(scores[key], min(0.75, 0.25 + hits * 0.10))

    if sentiment:
        sentiment_to_exposure = {
            "ai_demand_sentiment": "ai",
            "data_center_sentiment": "data_center",
            "automotive_demand_sentiment": "automotive",
            "consumer_demand_sentiment": "consumer",
            "industrial_demand_sentiment": "industrial",
            "memory_pricing_sentiment": "memory",
            "foundry_capacity_sentiment": "foundry",
            "semiconductor_capex_sentiment": "equipment",
            "optical_networking_sentiment": "optical",
        }
        for sentiment_key, exposure_key in sentiment_to_exposure.items():
            try:
                value = abs(float(sentiment.get(sentiment_key, 0) or 0))
            except (TypeError, ValueError):
                value = 0
            if value >= 0.25:
                scores[exposure_key] = max(scores[exposure_key], min(0.70, value + 0.20))

    return _clamp_scores(scores)
