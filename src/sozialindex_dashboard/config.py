from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from sozialindex_dashboard.db import ROOT_DIR

CONFIG_PATH = ROOT_DIR / "config.toml"
DEFAULT_SOCIALINDEX_PDF_URL = (
    "https://www.schulministerium.nrw/system/files/media/document/file/"
    "sozialindex_schulliste_schuljahr_2025-26.pdf"
)
DEFAULT_SCHOOL_BASE_DATA_URL = (
    "https://www.schulministerium.nrw.de/BiPo/OpenData/Schuldaten/schuldaten.csv"
)


@dataclass(frozen=True)
class SourceConfig:
    socialindex_pdf_url: str
    school_base_data_url: str


def load_source_config(config_path: Path = CONFIG_PATH) -> SourceConfig:
    if not config_path.exists():
        return SourceConfig(
            socialindex_pdf_url=DEFAULT_SOCIALINDEX_PDF_URL,
            school_base_data_url=DEFAULT_SCHOOL_BASE_DATA_URL,
        )

    with config_path.open("rb") as file:
        config = tomllib.load(file)

    sources = config.get("sources", {})
    socialindex_pdf_url = sources.get(
        "socialindex_pdf_url", DEFAULT_SOCIALINDEX_PDF_URL
    )
    school_base_data_url = sources.get(
        "school_base_data_url", DEFAULT_SCHOOL_BASE_DATA_URL
    )

    if not isinstance(socialindex_pdf_url, str) or not socialindex_pdf_url.strip():
        raise RuntimeError(
            "config.toml sources.socialindex_pdf_url must be a non-empty string."
        )
    if not isinstance(school_base_data_url, str) or not school_base_data_url.strip():
        raise RuntimeError(
            "config.toml sources.school_base_data_url must be a non-empty string."
        )

    return SourceConfig(
        socialindex_pdf_url=socialindex_pdf_url.strip(),
        school_base_data_url=school_base_data_url.strip(),
    )
