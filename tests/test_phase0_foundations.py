"""Phase 0 — fixtures, schemas, settings, dev CLI."""

from __future__ import annotations

import json
from pathlib import Path

import cli.__main__ as cli_main
from config import Settings, get_settings
from logging_context import new_run_id
from schemas.provenance import ProvenanceV1, provenance_from_raw_artifact
from schemas.raw_artifact import RawArtifact

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_JSON = REPO_ROOT / "fixtures" / "raw_artifacts.json"


def test_default_fixture_path_points_at_repo_fixtures() -> None:
    p = cli_main._default_fixture_path()
    assert p.name == "raw_artifacts.json"
    assert p.is_file()


def test_raw_artifacts_fixture_validates() -> None:
    rows = json.loads(FIXTURE_JSON.read_text(encoding="utf-8"))
    assert len(rows) >= 1
    for row in rows:
        RawArtifact.model_validate(row)


def test_provenance_from_first_fixture_row_has_required_keys() -> None:
    rows = json.loads(FIXTURE_JSON.read_text(encoding="utf-8"))
    art = RawArtifact.model_validate(rows[0])
    prov = provenance_from_raw_artifact(art)
    assert isinstance(prov, ProvenanceV1)
    d = prov.model_dump()
    for key in (
        "source_run_id",
        "collector_version",
        "extractor_model",
        "snippet_hash",
        "created_at",
        "ingested_at",
    ):
        assert key in d


def test_new_run_id_is_uuid_string() -> None:
    rid = new_run_id()
    assert len(rid) == 36
    assert rid != new_run_id()


def test_settings_default_data_dir(tmp_path: Path) -> None:
    s = Settings(DATA_DIR=str(tmp_path / "d"))
    assert s.data_dir == tmp_path / "d"


def test_get_settings_cached() -> None:
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b


def test_cli_validate_fixtures_zero_exit() -> None:
    assert cli_main.main(["validate-fixtures", "--path", str(FIXTURE_JSON)]) == 0


def test_cli_version() -> None:
    assert cli_main.main(["--version"]) == 0


def test_cli_module_version_string() -> None:
    assert cli_main.__version__.count(".") >= 1
