"""Relationship dataset builder for semiconductor and AI companies."""

from __future__ import annotations

import html
import os
import re
import time
import urllib.parse
import requests
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf
from tqdm import tqdm

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

from src.tickers import TICKERS

OUTPUT_COLUMNS = [
    "source_ticker",
    "source_company",
    "target_ticker",
    "target_company",
    "relationship_type",
    "direction",
    "strength_score",
    "confidence_score",
    "evidence_source",
    "evidence_text",
    "source_url",
    "notes",
]

ANNUAL_FORMS = ("10-K", "20-F", "40-F")
SEC_REQUEST_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "semiconductor-relationships-script/1.0",
)

# Extra companies requested for the relationship dataset.
BASE_COMPANIES = {
    # --- Newly tagged foundries ---
    "GFS": {
        "company_name": "GlobalFoundries Inc.",
        "aliases": ["GlobalFoundries", "Global Foundries"],
        "public_ticker": "GFS",
    },
    "TSEM": {
        "company_name": "Tower Semiconductor Ltd.",
        "aliases": ["Tower Semiconductor", "Tower Semi"],
        "public_ticker": "TSEM",
    },
    "AMKR": {
        "company_name": "Amkor Technology, Inc.",
        "aliases": ["Amkor", "Amkor Technology"],
        "public_ticker": "AMKR",
    },
    "IMOS": {
        "company_name": "ChipMOS Technologies Inc.",
        "aliases": ["ChipMOS", "ChipMOS Technologies"],
        "public_ticker": "IMOS",
    },
    "FLEX": {
        "company_name": "Flex Ltd.",
        "aliases": ["Flex", "Flex Ltd", "Flextronics"],
        "public_ticker": "FLEX",
    },
    "SANM": {
        "company_name": "Sanmina Corporation",
        "aliases": ["Sanmina"],
        "public_ticker": "SANM",
    },
    # --- Newly tagged equipment ---
    "COHU": {
        "company_name": "Cohu, Inc.",
        "aliases": ["Cohu"],
        "public_ticker": "COHU",
    },
    "FORM": {
        "company_name": "FormFactor, Inc.",
        "aliases": ["FormFactor"],
        "public_ticker": "FORM",
    },
    "VECO": {
        "company_name": "Veeco Instruments Inc.",
        "aliases": ["Veeco", "Veeco Instruments"],
        "public_ticker": "VECO",
    },
    "AEHR": {
        "company_name": "Aehr Test Systems",
        "aliases": ["Aehr", "Aehr Test"],
        "public_ticker": "AEHR",
    },
    "AEIS": {
        "company_name": "Advanced Energy Industries, Inc.",
        "aliases": ["Advanced Energy", "Advanced Energy Industries"],
        "public_ticker": "AEIS",
    },
    "IPGP": {
        "company_name": "IPG Photonics Corporation",
        "aliases": ["IPG Photonics", "IPG"],
        "public_ticker": "IPGP",
    },
    "PLAB": {
        "company_name": "Photronics, Inc.",
        "aliases": ["Photronics"],
        "public_ticker": "PLAB",
    },
    # --- Newly tagged IP ---
    "CEVA": {
        "company_name": "CEVA, Inc.",
        "aliases": ["CEVA"],
        "public_ticker": "CEVA",
    },
    "RMBS": {
        "company_name": "Rambus Inc.",
        "aliases": ["Rambus"],
        "public_ticker": "RMBS",
    },
    # --- Newly tagged server ---
    "PENG": {
        "company_name": "Penguin Solutions, Inc.",
        "aliases": ["Penguin Solutions", "Penguin Computing"],
        "public_ticker": "PENG",
    },
    # --- Newly tagged semiconductors ---
    "SWKS": {
        "company_name": "Skyworks Solutions, Inc.",
        "aliases": ["Skyworks", "Skyworks Solutions"],
        "public_ticker": "SWKS",
    },
    "QRVO": {
        "company_name": "Qorvo, Inc.",
        "aliases": ["Qorvo"],
        "public_ticker": "QRVO",
    },
    "CRUS": {
        "company_name": "Cirrus Logic, Inc.",
        "aliases": ["Cirrus Logic"],
        "public_ticker": "CRUS",
    },
    "LSCC": {
        "company_name": "Lattice Semiconductor Corporation",
        "aliases": ["Lattice", "Lattice Semiconductor"],
        "public_ticker": "LSCC",
    },
    "AMBA": {
        "company_name": "Ambarella, Inc.",
        "aliases": ["Ambarella"],
        "public_ticker": "AMBA",
    },
    "ALAB": {
        "company_name": "Astera Labs, Inc.",
        "aliases": ["Astera Labs"],
        "public_ticker": "ALAB",
    },
    "MTSI": {
        "company_name": "MACOM Technology Solutions Holdings, Inc.",
        "aliases": ["MACOM", "MACOM Technology"],
        "public_ticker": "MTSI",
    },
    "INDI": {
        "company_name": "indie Semiconductor, Inc.",
        "aliases": ["indie Semiconductor", "indie"],
        "public_ticker": "INDI",
    },
    "NVTS": {
        "company_name": "Navitas Semiconductor Limited",
        "aliases": ["Navitas", "Navitas Semiconductor"],
        "public_ticker": "NVTS",
    },
    "SLAB": {
        "company_name": "Silicon Laboratories Inc.",
        "aliases": ["Silicon Laboratories", "Silicon Labs"],
        "public_ticker": "SLAB",
    },
    "SMTC": {
        "company_name": "Semtech Corporation",
        "aliases": ["Semtech"],
        "public_ticker": "SMTC",
    },
    "DIOD": {
        "company_name": "Diodes Incorporated",
        "aliases": ["Diodes", "Diodes Incorporated"],
        "public_ticker": "DIOD",
    },
    "SYNA": {
        "company_name": "Synaptics Incorporated",
        "aliases": ["Synaptics"],
        "public_ticker": "SYNA",
    },
    "MXL": {
        "company_name": "MaxLinear, Inc.",
        "aliases": ["MaxLinear"],
        "public_ticker": "MXL",
    },
    "SIMO": {
        "company_name": "Silicon Motion Technology Corporation",
        "aliases": ["Silicon Motion"],
        "public_ticker": "SIMO",
    },
    "HIMX": {
        "company_name": "Himax Technologies, Inc.",
        "aliases": ["Himax", "Himax Technologies"],
        "public_ticker": "HIMX",
    },
    "ALGM": {
        "company_name": "Allegro MicroSystems, Inc.",
        "aliases": ["Allegro", "Allegro MicroSystems"],
        "public_ticker": "ALGM",
    },
    "SITM": {
        "company_name": "SiTime Corporation",
        "aliases": ["SiTime"],
        "public_ticker": "SITM",
    },
    "QUIK": {
        "company_name": "QuickLogic Corporation",
        "aliases": ["QuickLogic"],
        "public_ticker": "QUIK",
    },
    "MPWR": {
        "company_name": "Monolithic Power Systems, Inc.",
        "aliases": ["Monolithic Power Systems", "MPS"],
        "public_ticker": "MPWR",
    },
    # --- Memory ---
    "MRAM": {
        "company_name": "Everspin Technologies, Inc.",
        "aliases": ["Everspin", "Everspin Technologies"],
        "public_ticker": "MRAM",
    },
    # Extra companies requested for the relationship dataset.
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "aliases": ["NVIDIA", "NVIDIA Corporation"],
        "public_ticker": "NVDA",
    },
    "AMD": {
        "company_name": "Advanced Micro Devices, Inc.",
        "aliases": ["Advanced Micro Devices", "AMD"],
        "public_ticker": "AMD",
    },
    "AVGO": {
        "company_name": "Broadcom Inc.",
        "aliases": ["Broadcom", "Broadcom Inc."],
        "public_ticker": "AVGO",
    },
    "TSM": {
        "company_name": "Taiwan Semiconductor Manufacturing Company Limited",
        "aliases": [
            "Taiwan Semiconductor Manufacturing Company",
            "Taiwan Semiconductor",
            "TSMC",
        ],
        "public_ticker": "TSM",
    },
    "ASML": {
        "company_name": "ASML Holding N.V.",
        "aliases": ["ASML", "ASML Holding"],
        "public_ticker": "ASML",
    },
    "ARM": {
        "company_name": "Arm Holdings plc",
        "aliases": ["Arm Holdings", "Arm Limited", "Arm"],
        "public_ticker": "ARM",
    },
    "MU": {
        "company_name": "Micron Technology, Inc.",
        "aliases": ["Micron", "Micron Technology"],
        "public_ticker": "MU",
    },
    "MRVL": {
        "company_name": "Marvell Technology, Inc.",
        "aliases": ["Marvell", "Marvell Technology"],
        "public_ticker": "MRVL",
    },
    "QCOM": {
        "company_name": "QUALCOMM Incorporated",
        "aliases": ["Qualcomm", "QUALCOMM"],
        "public_ticker": "QCOM",
    },
    "INTC": {
        "company_name": "Intel Corporation",
        "aliases": ["Intel", "Intel Corporation"],
        "public_ticker": "INTC",
    },
    "AMAT": {
        "company_name": "Applied Materials, Inc.",
        "aliases": ["Applied Materials", "Applied Materials, Inc."],
        "public_ticker": "AMAT",
    },
    "LRCX": {
        "company_name": "Lam Research Corporation",
        "aliases": ["Lam Research", "Lam Research Corporation"],
        "public_ticker": "LRCX",
    },
    "KLAC": {
        "company_name": "KLA Corporation",
        "aliases": ["KLA", "KLA Corporation"],
        "public_ticker": "KLAC",
    },
    "TXN": {
        "company_name": "Texas Instruments Incorporated",
        "aliases": ["Texas Instruments", "Texas Instruments Incorporated"],
        "public_ticker": "TXN",
    },
    "ADI": {
        "company_name": "Analog Devices, Inc.",
        "aliases": ["Analog Devices", "Analog Devices, Inc."],
        "public_ticker": "ADI",
    },
    "ON": {
        "company_name": "ON Semiconductor Corporation",
        "aliases": ["ON Semiconductor", "onsemi", "onsemi corporation"],
        "public_ticker": "ON",
    },
    "MCHP": {
        "company_name": "Microchip Technology Incorporated",
        "aliases": ["Microchip", "Microchip Technology"],
        "public_ticker": "MCHP",
    },
    "NXPI": {
        "company_name": "NXP Semiconductors N.V.",
        "aliases": ["NXP", "NXP Semiconductors"],
        "public_ticker": "NXPI",
    },
    "TER": {
        "company_name": "Teradyne, Inc.",
        "aliases": ["Teradyne", "Teradyne, Inc."],
        "public_ticker": "TER",
    },
    "COHR": {
        "company_name": "Coherent Corp.",
        "aliases": ["Coherent", "Coherent Corp."],
        "public_ticker": "COHR",
    },
    "SMCI": {
        "company_name": "Super Micro Computer, Inc.",
        "aliases": ["Super Micro", "Supermicro", "Super Micro Computer"],
        "public_ticker": "SMCI",
    },
}

RELATION_KEYWORDS = {
    "foundry_supplier": [
        "foundry",
        "manufacturing partner",
        "manufacturing",
        "outsourced manufacturing",
        "wafer",
        "fabrication",
    ],
    "equipment_supplier": [
        "equipment",
        "lithography",
        "etch",
        "inspection",
        "deposition",
        "wafer",
        "customer",
    ],
    "memory_supplier": ["memory", "dram", "nand", "supplier", "supply"],
    "HBM_supplier": ["hbm", "high bandwidth memory", "memory", "dram"],
    "cloud_customer": [
        "cloud",
        "data center",
        "data centre",
        "hyperscale",
        "customer",
        "partner",
    ],
    "cloud_provider": [
        "cloud",
        "azure",
        "aws",
        "google cloud",
        "compute",
        "infrastructure",
    ],
    "AI_partner": ["ai", "artificial intelligence", "partner", "partnership", "collaboration"],
    "server_partner": ["server", "system", "platform", "solution", "supplier"],
    "EDA_supplier": [
        "eda",
        "design automation",
        "electronic design automation",
        "design tools",
        "software",
    ],
    "IP_supplier": [
        "ip",
        "intellectual property",
        "architecture",
        "license",
        "licensing",
    ],
    "customer": ["customer", "significant customer", "major customer"],
    "supplier": ["supplier", "suppliers", "vendor", "supply"],
    "competitor": ["compete", "competition", "competitors", "competing"],
    "strategic_partner": ["strategic partner", "partner", "partnership", "collaboration"],
    "ecosystem_link": [
        "ecosystem",
        "partner",
        "platform",
        "supply chain",
        "data center",
        "ai",
    ],
    "AI_accelerator_dependency": [
        "gpu",
        "accelerator",
        "compute",
        "training",
        "inference",
        "data center",
    ],
}

HIGH_SIGNAL_PHRASES = {
    "significant customer": 4,
    "major customer": 4,
    "third-party foundry": 4,
    "strategic partner": 3,
    "strategic partnership": 3,
    "high bandwidth memory": 3,
    "electronic design automation": 3,
}

SOURCE_PRIORITY = {"manual_seed": 1, "sec_filing": 2}

DISCOVERY_RELATION_TYPES = (
    "foundry_supplier",
    "equipment_supplier",
    "memory_supplier",
    "HBM_supplier",
    "cloud_customer",
    "AI_partner",
    "server_partner",
    "EDA_supplier",
    "IP_supplier",
    "customer",
    "supplier",
    "competitor",
    "strategic_partner",
    "ecosystem_link",
    "cloud_provider",
    "AI_accelerator_dependency",
)

RELATIONSHIP_DIRECTIONS = {
    "foundry_supplier": "upstream",
    "equipment_supplier": "upstream",
    "memory_supplier": "upstream",
    "HBM_supplier": "upstream",
    "EDA_supplier": "upstream",
    "IP_supplier": "upstream",
    "supplier": "upstream",
    "cloud_provider": "upstream",
    "AI_accelerator_dependency": "upstream",
    "customer": "downstream",
    "cloud_customer": "downstream",
    "AI_partner": "downstream",
    "server_partner": "downstream",
    "strategic_partner": "lateral",
    "ecosystem_link": "lateral",
    "competitor": "competitor",
}

RELATIONSHIP_BASE_STRENGTH = {
    "foundry_supplier": 4,
    "equipment_supplier": 3,
    "memory_supplier": 3,
    "HBM_supplier": 4,
    "cloud_customer": 3,
    "AI_partner": 3,
    "server_partner": 3,
    "EDA_supplier": 3,
    "IP_supplier": 4,
    "customer": 3,
    "supplier": 3,
    "competitor": 4,
    "strategic_partner": 3,
    "ecosystem_link": 2,
    "cloud_provider": 4,
    "AI_accelerator_dependency": 4,
}

GENERIC_RELATION_SUPPRESSION = {
    "customer": {
        "cloud_customer",
        "AI_partner",
        "server_partner",
        "cloud_provider",
        "foundry_supplier",
        "equipment_supplier",
        "memory_supplier",
        "HBM_supplier",
        "EDA_supplier",
        "IP_supplier",
    },
    "supplier": {
        "foundry_supplier",
        "equipment_supplier",
        "memory_supplier",
        "HBM_supplier",
        "EDA_supplier",
        "IP_supplier",
        "AI_accelerator_dependency",
    },
    "ecosystem_link": {"AI_partner", "server_partner", "strategic_partner", "cloud_customer"},
}

COMPANY_TAGS = {
    # --- Foundry / Wafer Manufacturing ---
    "TSM": "foundry",
    "GFS": "foundry",
    "TSEM": "foundry",
    "AMKR": "assembly",
    "IMOS": "assembly",
    "FLEX": "assembly",
    "KE": "assembly",
    "PLXS": "assembly",
    "SANM": "assembly",
    # --- Equipment / Process Tools ---
    "ASML": "equipment",
    "AMAT": "equipment",
    "LRCX": "equipment",
    "KLAC": "equipment",
    "TER": "equipment",
    "COHR": "equipment",
    "AAOI": "equipment",
    "AEHR": "equipment",
    "AEIS": "equipment",
    "COHU": "equipment",
    "CVV": "equipment",
    "FORM": "equipment",
    "IPGP": "equipment",
    "LASR": "equipment",
    "PLAB": "equipment",
    "VECO": "equipment",
    "AXTI": "equipment",
    # --- Memory ---
    "MU": "memory",
    "MRAM": "memory",
    # --- IP Licensing ---
    "ARM": "ip",
    "AIP": "ip",
    "CEVA": "ip",
    "RMBS": "ip",
    # --- Server / Systems ---
    "SMCI": "server",
    "PENG": "server",
    # --- Semiconductor (Fabless / IDM) ---
    "NVDA": "semiconductor",
    "AMD": "semiconductor",
    "AVGO": "semiconductor",
    "MRVL": "semiconductor",
    "QCOM": "semiconductor",
    "INTC": "semiconductor",
    "ADI": "semiconductor",
    "ON": "semiconductor",
    "MPWR": "semiconductor",
    "MCHP": "semiconductor",
    "MCHPP": "semiconductor",
    "NXPI": "semiconductor",
    "TXN": "semiconductor",
    "ALAB": "semiconductor",
    "ALGM": "semiconductor",
    "AMBA": "semiconductor",
    "AOSL": "semiconductor",
    "CRUS": "semiconductor",
    "DIOD": "semiconductor",
    "GSIT": "semiconductor",
    "HIMX": "semiconductor",
    "INDI": "semiconductor",
    "LEDS": "semiconductor",
    "LSCC": "semiconductor",
    "MOBX": "semiconductor",
    "MTSI": "semiconductor",
    "MXL": "semiconductor",
    "NVEC": "semiconductor",
    "NVTS": "semiconductor",
    "PI": "semiconductor",
    "POWI": "semiconductor",
    "PRSO": "semiconductor",
    "PXLW": "semiconductor",
    "QRVO": "semiconductor",
    "QUIK": "semiconductor",
    "SIMO": "semiconductor",
    "SITM": "semiconductor",
    "SLAB": "semiconductor",
    "SMTC": "semiconductor",
    "SMTK": "semiconductor",
    "SWKS": "semiconductor",
    "SYNA": "semiconductor",
    "LFUS": "semiconductor",
    "LNKS": "semiconductor",
    # --- Device / Sensor / Component ---
    "AEVA": "device",
    "AIRG": "device",
    "AMPG": "device",
    "BOSC": "device",
    "HOLO": "device",
    "IMTE": "device",
    "INVE": "device",
    "KOPN": "device",
    "LINK": "device",
    "MVIS": "device",
    "NEON": "device",
    "OESX": "device",
    "OLED": "device",
    "OUST": "device",
    "RELL": "device",
    "TOYO": "device",
    "WATT": "device",
    "WKEY": "device",
    # --- Energy / Solar ---
    "ASTI": "energy",
    "CSIQ": "energy",
    "ENGS": "energy",
    "FSLR": "energy",
    "PLUG": "energy",
    "RUN": "energy",
    "SHLS": "energy",
    "TYGO": "energy",
    # --- Other ---
    "AUID": "device",
    "DVLT": "device",
    "GSIT": "memory",
    "IPWR": "semiconductor",
    "LAES": "device",
    "NA": "device",
}

# Minimum manual seed rows requested by the user.
MANUAL_SEED_RELATIONSHIPS = [
    # --- New foundry seeds ---
    ("GFS", "ASML", "equipment_supplier", "upstream", 4),
    ("GFS", "AMAT", "equipment_supplier", "upstream", 4),
    ("GFS", "LRCX", "equipment_supplier", "upstream", 4),
    ("GFS", "KLAC", "equipment_supplier", "upstream", 4),
    ("GFS", "TSM", "competitor", "competitor", 4),
    ("TSEM", "AMAT", "equipment_supplier", "upstream", 3),
    ("TSEM", "KLAC", "equipment_supplier", "upstream", 3),
    ("TSEM", "TSM", "competitor", "competitor", 3),
    # --- New packaging/assembly seeds ---
    ("AMKR", "NVDA", "customer", "downstream", 4),
    ("AMKR", "AMD", "customer", "downstream", 3),
    ("AMKR", "QCOM", "customer", "downstream", 3),
    ("AMKR", "TSM", "strategic_partner", "lateral", 3),
    ("IMOS", "NVDA", "customer", "downstream", 2),
    ("IMOS", "AMD", "customer", "downstream", 2),
    # --- New semiconductor seeds ---
    ("SWKS", "QCOM", "strategic_partner", "lateral", 4),
    ("SWKS", "TSM", "foundry_supplier", "upstream", 4),
    ("SWKS", "QRVO", "competitor", "competitor", 4),
    ("QRVO", "TSM", "foundry_supplier", "upstream", 4),
    ("QRVO", "AVGO", "competitor", "competitor", 3),
    ("QRVO", "SWKS", "competitor", "competitor", 4),
    ("CRUS", "TSM", "foundry_supplier", "upstream", 3),
    ("LSCC", "TSM", "foundry_supplier", "upstream", 3),
    ("LSCC", "INTC", "competitor", "competitor", 3),
    ("AMBA", "TSM", "foundry_supplier", "upstream", 3),
    ("MTSI", "TSM", "foundry_supplier", "upstream", 3),
    ("INDI", "TSM", "foundry_supplier", "upstream", 3),
    ("SLAB", "TSM", "foundry_supplier", "upstream", 3),
    ("NVTS", "TSM", "foundry_supplier", "upstream", 3),
    ("SMTC", "TSM", "foundry_supplier", "upstream", 3),
    ("ALAB", "TSM", "foundry_supplier", "upstream", 3),
    ("ALAB", "NVDA", "ecosystem_link", "lateral", 3),
    ("SITM", "TSM", "foundry_supplier", "upstream", 3),
    ("SYNA", "TSM", "foundry_supplier", "upstream", 3),
    ("MXL", "TSM", "foundry_supplier", "upstream", 3),
    ("SIMO", "TSM", "foundry_supplier", "upstream", 3),
    ("HIMX", "TSM", "foundry_supplier", "upstream", 3),
    ("DIOD", "TSM", "foundry_supplier", "upstream", 2),
    ("MPWR", "TSM", "foundry_supplier", "upstream", 3),
    # --- New IP seeds ---
    ("CEVA", "QCOM", "IP_supplier", "downstream", 3),
    ("CEVA", "MRVL", "IP_supplier", "downstream", 3),
    ("RMBS", "MU", "IP_supplier", "downstream", 4),
    ("RMBS", "AMD", "IP_supplier", "downstream", 3),
    ("RMBS", "INTC", "IP_supplier", "downstream", 3),
    # --- New server seeds ---
    ("PENG", "NVDA", "supplier", "upstream", 3),
    ("PENG", "AMD", "supplier", "upstream", 2),
    # --- New equipment seeds ---
    ("VECO", "TSM", "customer", "downstream", 3),
    ("VECO", "INTC", "customer", "downstream", 3),
    ("AEIS", "TSM", "customer", "downstream", 3),
    ("AEIS", "LRCX", "strategic_partner", "lateral", 3),
    ("AEIS", "AMAT", "strategic_partner", "lateral", 3),
    ("FORM", "TSM", "customer", "downstream", 3),
    ("FORM", "NVDA", "customer", "downstream", 3),
    ("COHU", "TSM", "customer", "downstream", 3),
    ("PLAB", "TSM", "customer", "downstream", 3),
    ("PLAB", "INTC", "customer", "downstream", 3),
    # --- Existing seeds (kept) ---
    ("NVDA", "TSM", "foundry_supplier", "upstream", 5),
    ("NVDA", "MU", "memory_supplier", "upstream", 3),
    ("NVDA", "SMCI", "server_partner", "downstream", 4),
    ("NVDA", "AMD", "competitor", "competitor", 5),
    ("AMD", "TSM", "foundry_supplier", "upstream", 5),
    ("AMD", "MU", "memory_supplier", "upstream", 3),
    ("AMD", "NVDA", "competitor", "competitor", 5),
    ("AMD", "INTC", "competitor", "competitor", 5),
    ("TSM", "ASML", "equipment_supplier", "upstream", 5),
    ("TSM", "AMAT", "equipment_supplier", "upstream", 4),
    ("TSM", "LRCX", "equipment_supplier", "upstream", 4),
    ("TSM", "KLAC", "equipment_supplier", "upstream", 4),
    ("TSM", "NVDA", "customer", "downstream", 5),
    ("TSM", "AMD", "customer", "downstream", 5),
    ("TSM", "QCOM", "customer", "downstream", 4),
    ("TSM", "AVGO", "customer", "downstream", 4),
    ("ASML", "TSM", "customer", "downstream", 5),
    ("ASML", "INTC", "customer", "downstream", 5),
    ("AVGO", "TSM", "foundry_supplier", "upstream", 4),
    ("AVGO", "MRVL", "competitor", "competitor", 4),
    ("MRVL", "TSM", "foundry_supplier", "upstream", 3),
    ("MRVL", "AVGO", "competitor", "competitor", 4),
    ("MU", "NVDA", "HBM_supplier", "downstream", 3),
    ("MU", "AMD", "HBM_supplier", "downstream", 3),
    ("SMCI", "NVDA", "supplier", "upstream", 5),
    ("SMCI", "AMD", "supplier", "upstream", 3),
    ("SMCI", "INTC", "supplier", "upstream", 3),
    ("ARM", "QCOM", "IP_supplier", "downstream", 5),
    ("ARM", "NVDA", "ecosystem_link", "lateral", 3),
    ("COHR", "NVDA", "ecosystem_link", "lateral", 2),
    ("COHR", "AVGO", "ecosystem_link", "lateral", 2),
    ("COHR", "MRVL", "ecosystem_link", "lateral", 2),
]


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    company_name: str
    aliases: tuple[str, ...]
    public_ticker: str | None


@dataclass
class FilingDocument:
    ticker: str
    form_type: str
    source_url: str
    source_label: str
    text: str
    segments: list[str]


def _build_company_registry() -> dict[str, CompanyProfile]:
    registry: dict[str, CompanyProfile] = {}

    for ticker in TICKERS:
        if ticker in BASE_COMPANIES:
            metadata = BASE_COMPANIES[ticker]
        else:
            metadata = {
                "company_name": ticker,
                "aliases": [ticker],
                "public_ticker": ticker,
            }

        aliases = tuple(dict.fromkeys([metadata["company_name"], *metadata["aliases"]]))
        registry[ticker] = CompanyProfile(
            ticker=ticker,
            company_name=metadata["company_name"],
            aliases=aliases,
            public_ticker=metadata.get("public_ticker"),
        )

    return registry


def _truncate_text(text: str, max_length: int = 300) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def _manual_confidence_score(strength_score: int) -> int:
    if strength_score >= 4:
        return 3
    if strength_score >= 2:
        return 2
    return 1


def _manual_evidence_text(source_ticker: str, target_ticker: str, relationship_type: str) -> str:
    return _truncate_text(
        f"Manual seed fallback for {source_ticker} -> {target_ticker} "
        f"({relationship_type}) pending stronger public-source confirmation."
    )


@lru_cache(maxsize=None)
def _compile_alias_patterns(aliases: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for alias in aliases:
        normalized_alias = alias.strip().lower()
        if len(normalized_alias) <= 2:
            continue
        patterns.append(re.compile(r"\b" + re.escape(normalized_alias) + r"\b", re.IGNORECASE))
    return tuple(patterns)


def _split_filing_locator(filing_entry: dict[str, Any]) -> tuple[str, str] | None:
    edgar_url = str(filing_entry.get("edgarUrl", "")).rstrip("/")
    if not edgar_url:
        return None

    slug = edgar_url.split("/")[-1]
    if "_" not in slug:
        return None

    accession_number, cik = slug.split("_", maxsplit=1)
    return accession_number, cik


def _resolve_filing_source_urls(filing_entry: dict[str, Any]) -> list[tuple[str, str]]:
    form_type = str(filing_entry.get("type", "")).strip()
    exhibits = filing_entry.get("exhibits") or {}
    locator = _split_filing_locator(filing_entry)
    urls: list[tuple[str, str]] = []

    if locator and isinstance(exhibits, dict):
        accession_number, cik = locator
        primary_document_url = exhibits.get(form_type)
        if primary_document_url:
            document_name = str(primary_document_url).rstrip("/").split("/")[-1]
            sec_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_number.replace('-', '')}/{document_name}"
            )
            urls.append((sec_url, "sec_archive"))
            urls.append((str(primary_document_url), "yahoo_sec_mirror"))

    return urls


MAX_FILING_BYTES = 1_500_000  # read at most 1.5 MB per filing


def _fetch_url_text(url: str) -> str | None:
    request = Request(url, headers={"User-Agent": SEC_REQUEST_USER_AGENT})
    try:
        with urlopen(request, timeout=15) as response:
            return response.read(MAX_FILING_BYTES).decode("utf-8", errors="ignore")
    except Exception:
        # Catches HTTPError, URLError, TimeoutError, RemoteDisconnected, etc.
        return None


def _html_to_segments(raw_html: str) -> list[str]:
    html_text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    html_text = re.sub(r"(?i)</(div|p|li|tr|table|section|h1|h2|h3|h4|h5|h6|br)>", "\n", html_text)
    html_text = re.sub(r"(?is)<.*?>", " ", html_text)
    html_text = html.unescape(html_text)

    lines = [re.sub(r"\s+", " ", line).strip() for line in html_text.splitlines()]
    segments: list[str] = []

    for line in lines:
        if len(line) < 20:
            continue

        lowered_line = line.lower()
        if (
            lowered_line.count("http://") + lowered_line.count("https://") >= 1
            and len(line) > 120
        ):
            continue
        if any(
            noisy_token in lowered_line
            for noisy_token in ("xmlns", "www.xbrl", "iso4217", "xlink", "us-gaap", "ifrs")
        ):
            continue

        if len(line) > 500:
            sentence_parts = re.split(r"(?<=[.!?;:])\s+", line)
            for sentence in sentence_parts:
                cleaned_sentence = re.sub(r"\s+", " ", sentence).strip()
                if len(cleaned_sentence) >= 20:
                    segments.append(cleaned_sentence)
        else:
            segments.append(line)

    return segments


def _contains_alias(segment: str, aliases: tuple[str, ...]) -> tuple[bool, int]:
    hit_count = 0
    for alias_pattern in _compile_alias_patterns(aliases):
        if alias_pattern.search(segment):
            hit_count += 1
    return hit_count > 0, hit_count


def _score_segment(
    segment: str, target_aliases: tuple[str, ...], relation_type: str
) -> tuple[int, int, int]:
    segment_lower = segment.lower()
    has_alias, alias_count = _contains_alias(segment, target_aliases)
    if not has_alias:
        return 0, 0, 0

    keyword_hits = sum(
        1 for keyword in RELATION_KEYWORDS.get(relation_type, []) if keyword.lower() in segment_lower
    )
    phrase_bonus = sum(
        weight for phrase, weight in HIGH_SIGNAL_PHRASES.items() if phrase in segment_lower
    )

    # Alias-only hits are too noisy for relationship discovery.
    if keyword_hits == 0 and phrase_bonus == 0:
        return 0, 0, 0

    score = alias_count * 2 + keyword_hits * 2 + phrase_bonus
    if relation_type == "competitor" and "compete" in segment_lower:
        score += 2

    if relation_type in {"customer", "supplier"} and "customer" in segment_lower:
        score += 2

    if relation_type == "foundry_supplier" and "foundry" in segment_lower:
        score += 2

    return score, keyword_hits, phrase_bonus


def _match_confidence(score: int, keyword_hits: int) -> int:
    if score >= 10 or keyword_hits >= 3:
        return 5
    if score >= 6 or keyword_hits >= 1:
        return 4
    return 3


def _find_best_evidence_segment(
    segments: list[str], target_aliases: tuple[str, ...], relation_type: str
) -> dict[str, Any] | None:
    best_match: dict[str, Any] | None = None

    for segment in segments:
        score, keyword_hits, phrase_bonus = _score_segment(segment, target_aliases, relation_type)
        if score <= 0:
            continue

        match = {
            "score": score,
            "keyword_hits": keyword_hits,
            "phrase_bonus": phrase_bonus,
            "evidence_text": _truncate_text(segment),
            "confidence_score": _match_confidence(score, keyword_hits),
        }

        if best_match is None or (
            match["score"],
            match["confidence_score"],
            len(match["evidence_text"]),
        ) > (
            best_match["score"],
            best_match["confidence_score"],
            len(best_match["evidence_text"]),
        ):
            best_match = match

    return best_match


def _latest_annual_filing(public_ticker: str) -> dict[str, Any] | None:
    try:
        filings = yf.Ticker(public_ticker).get_sec_filings()
    except Exception:
        return None

    if not filings:
        return None

    for filing_entry in filings:
        if str(filing_entry.get("type", "")).strip() in ANNUAL_FORMS:
            return filing_entry
    return None


def _load_filing_document(public_ticker: str) -> FilingDocument | None:
    filing_entry = _latest_annual_filing(public_ticker)
    if filing_entry is None:
        return None

    form_type = str(filing_entry.get("type", "")).strip()
    for url, source_label in _resolve_filing_source_urls(filing_entry):
        raw_text = _fetch_url_text(url)
        if not raw_text:
            continue

        segments = _html_to_segments(raw_text)
        if not segments:
            continue

        return FilingDocument(
            ticker=public_ticker,
            form_type=form_type,
            source_url=url,
            source_label=source_label,
            text=raw_text,
            segments=segments,
        )

    return None


def _relationship_direction(
    relationship_type: str, source_ticker: str | None = None, target_ticker: str | None = None
) -> str:
    source_tag = COMPANY_TAGS.get(source_ticker or "")
    target_tag = COMPANY_TAGS.get(target_ticker or "")

    if relationship_type in {
        "foundry_supplier",
        "equipment_supplier",
        "memory_supplier",
        "HBM_supplier",
        "EDA_supplier",
        "IP_supplier",
        "supplier",
    }:
        if source_tag in {"memory", "equipment", "eda", "ip", "server"} and target_tag in {
            "semiconductor",
            "device",
            "foundry",
            "cloud",
            "server",
        }:
            return "downstream"
        return "upstream"

    if relationship_type in {"customer", "cloud_customer", "AI_partner", "server_partner"}:
        return "downstream"

    return RELATIONSHIP_DIRECTIONS.get(relationship_type, "lateral")


def _allowed_discovery_relations(source_ticker: str, target_ticker: str) -> set[str]:
    source_tag = COMPANY_TAGS.get(source_ticker)
    target_tag = COMPANY_TAGS.get(target_ticker)

    if target_tag == "ai_lab":
        return set()

    if source_tag == "semiconductor":
        if target_tag == "foundry":
            return {"foundry_supplier"}
        if target_tag == "assembly":
            return {"strategic_partner"}
        if target_tag == "memory":
            return {"HBM_supplier", "memory_supplier", "competitor"}
        if target_tag == "cloud":
            return {"cloud_customer", "strategic_partner"}
        if target_tag == "eda":
            return {"EDA_supplier"}
        if target_tag == "ip":
            return {"IP_supplier"}
        if target_tag == "server":
            return {"server_partner", "ecosystem_link"}
        if target_tag == "semiconductor":
            return {"competitor", "strategic_partner", "ecosystem_link"}
        if target_tag == "equipment":
            return {"strategic_partner"}
        if target_tag in {"device", "energy"}:
            return {"strategic_partner", "ecosystem_link"}
        return set()

    if source_tag == "foundry":
        if target_tag == "equipment":
            return {"equipment_supplier"}
        if target_tag in {"semiconductor", "device"}:
            return {"customer", "strategic_partner"}
        if target_tag == "foundry":
            return {"competitor", "strategic_partner"}
        if target_tag == "assembly":
            return {"strategic_partner"}
        if target_tag == "memory":
            return {"customer"}
        return set()

    if source_tag == "assembly":
        if target_tag in {"semiconductor", "foundry"}:
            return {"customer", "strategic_partner"}
        if target_tag == "assembly":
            return {"competitor", "strategic_partner"}
        if target_tag == "equipment":
            return {"equipment_supplier"}
        return set()

    if source_tag == "equipment":
        if target_tag in {"foundry", "memory", "semiconductor", "assembly"}:
            return {"customer"}
        if target_tag == "equipment":
            return {"competitor", "strategic_partner"}
        return set()

    if source_tag == "memory":
        if target_tag in {"semiconductor", "server", "device"}:
            return {"HBM_supplier", "memory_supplier", "customer"}
        if target_tag == "memory":
            return {"competitor"}
        if target_tag == "equipment":
            return {"customer"}
        return set()

    if source_tag == "eda":
        if target_tag in {"semiconductor", "foundry", "device"}:
            return {"EDA_supplier", "customer"}
        if target_tag == "eda":
            return {"competitor"}
        return set()

    if source_tag == "ip":
        if target_tag in {"semiconductor", "device", "foundry"}:
            return {"IP_supplier", "customer", "strategic_partner"}
        if target_tag == "ip":
            return {"competitor"}
        if target_tag == "memory":
            return {"IP_supplier", "customer"}
        return set()

    if source_tag == "server":
        if target_tag == "semiconductor":
            return {"supplier", "strategic_partner", "AI_accelerator_dependency"}
        if target_tag == "server":
            return {"competitor"}
        if target_tag == "memory":
            return {"memory_supplier"}
        return set()

    if source_tag == "device":
        if target_tag in {"semiconductor", "foundry"}:
            return {"customer", "strategic_partner"}
        if target_tag == "device":
            return {"competitor", "strategic_partner"}
        if target_tag == "equipment":
            return {"strategic_partner"}
        return set()

    if source_tag == "energy":
        if target_tag in {"semiconductor", "foundry"}:
            return {"customer", "strategic_partner"}
        if target_tag == "energy":
            return {"competitor"}
        return set()

    return set()


def _relationship_strength(
    relationship_type: str, score: int, keyword_hits: int, phrase_bonus: int
) -> int:
    strength = RELATIONSHIP_BASE_STRENGTH.get(relationship_type, 2)
    if phrase_bonus >= 4:
        strength = max(strength, 5)
    elif phrase_bonus >= 3 or keyword_hits >= 3 or score >= 10:
        strength = min(5, strength + 1)
    elif keyword_hits == 1 and strength > 1:
        strength = max(1, strength)
    return max(1, min(5, strength))


def _sec_notes(source_role: str, filing_document: FilingDocument) -> str:
    notes = f"Auto-discovered from {source_role} annual filing ({filing_document.form_type})."
    if filing_document.source_label == "yahoo_sec_mirror":
        notes += " SEC archive request was unavailable in this runtime, so a filing mirror URL was used."
    return notes


def _discovered_row_sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    evidence_priority = SOURCE_PRIORITY.get(str(row["evidence_source"]), 0)
    return (
        evidence_priority,
        int(row["confidence_score"]),
        int(row["strength_score"]),
    )


def _suppress_generic_pair_relations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_pair.setdefault((row["source_ticker"], row["target_ticker"]), []).append(row)

    kept_rows: list[dict[str, Any]] = []
    for pair_rows in rows_by_pair.values():
        pair_relation_types = {row["relationship_type"] for row in pair_rows}
        for row in pair_rows:
            suppressed_by = GENERIC_RELATION_SUPPRESSION.get(row["relationship_type"], set())
            if pair_relation_types.intersection(suppressed_by):
                continue
            kept_rows.append(row)

    return kept_rows



@lru_cache(maxsize=1000)
def _resolve_ticker(company_name: str) -> str | None:
    ignore_list = ["the sec", "sec", "fasb", "gaap", "u.s.", "the united states", "inc.", "corp.", "ltd."]
    if company_name.lower() in ignore_list or len(company_name) < 3:
        return None
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(company_name)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            quotes = data.get("quotes", [])
            if quotes and "symbol" in quotes[0] and not "." in quotes[0]["symbol"]:
                return quotes[0]["symbol"]
    except Exception:
        pass
    return None

def _discover_relationship_rows_for_source(
    source_profile: CompanyProfile,
    registry: dict[str, CompanyProfile],
    filing_document: FilingDocument,
) -> tuple[list[dict[str, Any]], set[str]]:
    best_matches: dict[tuple[str, str], dict[str, Any]] = {}
    new_tickers_discovered = set()

    for segment in filing_document.segments:
        for target_profile in registry.values():
            if target_profile.ticker == source_profile.ticker:
                continue

            has_alias, _alias_count = _contains_alias(segment, target_profile.aliases)
            if not has_alias:
                continue

            allowed_relation_types = _allowed_discovery_relations(
                source_profile.ticker, target_profile.ticker
            )
            if not allowed_relation_types:
                continue

            for relationship_type in DISCOVERY_RELATION_TYPES:
                if relationship_type not in allowed_relation_types:
                    continue

                score, keyword_hits, phrase_bonus = _score_segment(
                    segment, target_profile.aliases, relationship_type
                )
                if score <= 0:
                    continue

                confidence_score = _match_confidence(score, keyword_hits)
                if confidence_score < 4 and phrase_bonus < 3:
                    continue

                candidate_row = {
                    "source_ticker": source_profile.ticker,
                    "source_company": source_profile.company_name,
                    "target_ticker": target_profile.ticker,
                    "target_company": target_profile.company_name,
                    "relationship_type": relationship_type,
                    "direction": _relationship_direction(
                        relationship_type, source_profile.ticker, target_profile.ticker
                    ),
                    "strength_score": _relationship_strength(
                        relationship_type, score, keyword_hits, phrase_bonus
                    ),
                    "confidence_score": confidence_score,
                    "evidence_source": "sec_filing",
                    "evidence_text": _truncate_text(segment),
                    "source_url": filing_document.source_url,
                    "notes": _sec_notes("source", filing_document),
                }

                match_key = (target_profile.ticker, relationship_type)
                current_best = best_matches.get(match_key)
                if current_best is None or _discovered_row_sort_key(candidate_row) > _discovered_row_sort_key(
                    current_best
                ):
                    best_matches[match_key] = candidate_row
                    
        if nlp is not None:
            has_keyword = False
            for keywords in RELATION_KEYWORDS.values():
                if any(kw in segment.lower() for kw in keywords):
                    has_keyword = True
                    break
            
            if has_keyword:
                doc = nlp(segment)
                for ent in doc.ents:
                    if ent.label_ == "ORG" and ent.text.lower() not in source_profile.company_name.lower():
                        if len(ent.text) > 3:
                            ticker = _resolve_ticker(ent.text)
                            if ticker and ticker not in registry:
                                new_tickers_discovered.add(ticker)

    discovered_rows = list(best_matches.values())
    return _suppress_generic_pair_relations(discovered_rows), new_tickers_discovered


def _discover_relationship_rows(registry: dict[str, CompanyProfile]) -> list[dict[str, Any]]:
    """Flat scan: download and parse the latest annual filing for every ticker in
    TICKERS (not just NVDA), then extract relationship evidence from the text.
    Uses a thread pool to parallelize filing downloads.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    filing_cache: dict[str, FilingDocument | None] = {}
    filing_lock = threading.Lock()
    discovered_rows: list[dict[str, Any]] = []

    def _fetch_filing(source_ticker: str) -> tuple[str, FilingDocument | None]:
        try:
            if source_ticker not in registry:
                registry[source_ticker] = CompanyProfile(
                    ticker=source_ticker,
                    company_name=source_ticker,
                    aliases=(source_ticker,),
                    public_ticker=source_ticker,
                )
            source_profile = registry[source_ticker]
            if not source_profile.public_ticker:
                return source_ticker, None
            doc = _load_filing_document(source_profile.public_ticker)
            time.sleep(0.2)  # gentle rate-limit per thread
            return source_ticker, doc
        except Exception:
            return source_ticker, None

    tickers_to_scan = list(TICKERS)

    print(f"Downloading SEC filings for {len(tickers_to_scan)} tickers (parallel)...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_filing, t): t for t in tickers_to_scan}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Downloading filings"):
            source_ticker, doc = future.result()
            with filing_lock:
                filing_cache[source_ticker] = doc

    print("Extracting relationships from filings...")

    def _extract_rows(source_ticker: str) -> list[dict[str, Any]]:
        try:
            source_profile = registry.get(source_ticker)
            if source_profile is None:
                return []
            filing_document = filing_cache.get(source_ticker)
            if filing_document is None:
                return []
            rows, _ = _discover_relationship_rows_for_source(
                source_profile, registry, filing_document
            )
            return rows
        except Exception:
            return []

    all_results: list[list[dict[str, Any]]] = [None] * len(tickers_to_scan)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_extract_rows, t): i for i, t in enumerate(tickers_to_scan)}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Scanning SEC filings"):
            idx = futures[future]
            all_results[idx] = future.result()

    for rows in all_results:
        if rows:
            discovered_rows.extend(rows)

    return discovered_rows


def _seed_records(registry: dict[str, CompanyProfile]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for source_ticker, target_ticker, relationship_type, direction, strength_score in (
        MANUAL_SEED_RELATIONSHIPS
    ):
        source_profile = registry[source_ticker]
        target_profile = registry[target_ticker]

        rows.append(
            {
                "source_ticker": source_profile.ticker,
                "source_company": source_profile.company_name,
                "target_ticker": target_profile.ticker,
                "target_company": target_profile.company_name,
                "relationship_type": relationship_type,
                "direction": direction,
                "strength_score": int(strength_score),
                "confidence_score": _manual_confidence_score(int(strength_score)),
                "evidence_source": "manual_seed",
                "evidence_text": _manual_evidence_text(
                    source_profile.ticker, target_profile.ticker, relationship_type
                ),
                "source_url": "",
                "notes": "Manual seed fallback; review against SEC or official company sources.",
            }
        )

    return rows


def _try_enrich_row_with_filing(
    row: dict[str, Any],
    source_role: str,
    counterparty_profile: CompanyProfile,
    filing_cache: dict[str, FilingDocument | None],
    registry: dict[str, CompanyProfile],
) -> dict[str, Any] | None:
    search_ticker = row["source_ticker"] if source_role == "source" else row["target_ticker"]
    search_profile = registry[search_ticker]

    if not search_profile.public_ticker:
        return None

    if search_profile.public_ticker not in filing_cache:
        filing_cache[search_profile.public_ticker] = _load_filing_document(search_profile.public_ticker)
        time.sleep(0.1)

    filing_document = filing_cache.get(search_profile.public_ticker)
    if filing_document is None:
        return None

    match = _find_best_evidence_segment(
        filing_document.segments,
        counterparty_profile.aliases,
        row["relationship_type"],
    )
    if match is None:
        return None

    notes = f"Matched in {source_role} annual filing ({filing_document.form_type})."
    if filing_document.source_label == "yahoo_sec_mirror":
        notes += " SEC archive request was unavailable in this runtime, so a filing mirror URL was used."

    enriched_row = row.copy()
    enriched_row.update(
        {
            "confidence_score": max(int(row["confidence_score"]), int(match["confidence_score"])),
            "evidence_source": "sec_filing",
            "evidence_text": match["evidence_text"],
            "source_url": filing_document.source_url,
            "notes": notes,
        }
    )
    return enriched_row


def _enrich_relationship_rows(
    seed_rows: list[dict[str, Any]], registry: dict[str, CompanyProfile]
) -> list[dict[str, Any]]:
    filing_cache: dict[str, FilingDocument | None] = {}
    enriched_rows: list[dict[str, Any]] = []

    for row in tqdm(seed_rows, desc="Building relationships"):
        best_row = row

        source_match = _try_enrich_row_with_filing(
            row=row,
            source_role="source",
            counterparty_profile=registry[row["target_ticker"]],
            filing_cache=filing_cache,
            registry=registry,
        )
        if source_match is not None:
            best_row = source_match

        target_match = _try_enrich_row_with_filing(
            row=row,
            source_role="target",
            counterparty_profile=registry[row["source_ticker"]],
            filing_cache=filing_cache,
            registry=registry,
        )
        if target_match is not None:
            current_priority = (
                SOURCE_PRIORITY[best_row["evidence_source"]],
                int(best_row["confidence_score"]),
            )
            target_priority = (
                SOURCE_PRIORITY[target_match["evidence_source"]],
                int(target_match["confidence_score"]),
            )
            if target_priority > current_priority:
                best_row = target_match

        enriched_rows.append(best_row)

    return enriched_rows


def _deduplicate_relationship_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df["_source_priority"] = df["evidence_source"].map(SOURCE_PRIORITY).fillna(0)

    df = df.sort_values(
        [
            "source_ticker",
            "target_ticker",
            "relationship_type",
            "_source_priority",
            "confidence_score",
            "strength_score",
        ],
        ascending=[True, True, True, False, False, False],
    )

    df = df.drop_duplicates(
        subset=["source_ticker", "target_ticker", "relationship_type"],
        keep="first",
    )

    df = df.drop(columns="_source_priority")
    df = df.sort_values(
        ["source_ticker", "strength_score", "confidence_score", "target_ticker"],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)

    return df[OUTPUT_COLUMNS]


def build_company_relationships_dataframe() -> pd.DataFrame:
    """Create the relationship dataset with SEC-backed evidence where available."""

    registry = _build_company_registry()
    seed_rows = _seed_records(registry)
    discovered_rows = _discover_relationship_rows(registry)
    enriched_rows = _enrich_relationship_rows(seed_rows, registry)
    return _deduplicate_relationship_rows(discovered_rows + enriched_rows)
