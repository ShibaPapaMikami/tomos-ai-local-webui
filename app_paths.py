from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


APPLICATION_SUPPORT_RELATIVE_PATH = Path("Library/Application Support/com.shibapapastudio.tomos-ai")
RESOURCE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TomosPaths:
    root: Path
    knowledge_db: Path
    context_db: Path
    contracts_db: Path
    study_packs: Path
    person_photos: Path
    codegraph: Path
    logs: Path
    migration: Path

    @classmethod
    def from_root(cls, root: Path) -> "TomosPaths":
        root = Path(root)
        data = root / "data"
        return cls(
            root=root,
            knowledge_db=data / "knowledge" / "index.sqlite",
            context_db=data / "memory" / "context.sqlite",
            contracts_db=data / "contracts" / "contracts.sqlite",
            study_packs=data / "study-packs",
            person_photos=data / "person-photos",
            codegraph=data / "codegraph",
            logs=root / "logs",
            migration=root / "migration",
        )


def tomos_data_root(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    values = os.environ if env is None else env
    override = values.get("TOMOS_DATA_ROOT")
    if override is not None:
        candidate_value = str(override).strip()
        if not candidate_value:
            raise ValueError("TOMOS_DATA_ROOT must not be empty")
        candidate = Path(candidate_value)
        if not candidate.is_absolute():
            raise ValueError("TOMOS_DATA_ROOT must be an absolute path")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(RESOURCE_ROOT)
        except ValueError:
            return candidate
        raise ValueError("TOMOS_DATA_ROOT must be outside the application bundle")
    return Path.home() / APPLICATION_SUPPORT_RELATIVE_PATH if home is None else Path(home) / APPLICATION_SUPPORT_RELATIVE_PATH


def ensure_data_directories(paths: TomosPaths) -> None:
    for directory in (
        paths.knowledge_db.parent,
        paths.context_db.parent,
        paths.contracts_db.parent,
        paths.study_packs,
        paths.person_photos,
        paths.codegraph,
        paths.logs,
        paths.migration,
    ):
        directory.mkdir(parents=True, exist_ok=True)
