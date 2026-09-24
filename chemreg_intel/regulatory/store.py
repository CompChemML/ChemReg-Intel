from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metadata import AuthorityLevel, DatasetSnapshot, SourceMetadata, ValidationReport


class DatasetStore:
    """Immutable, content-addressed regulatory snapshots in local SQLite storage."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blob_dir = self.root / "blobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.root / "regulatory_snapshots.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    adapter_id TEXT NOT NULL,
                    retrieval_timestamp TEXT NOT NULL,
                    effective_date TEXT,
                    version TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    raw_filename TEXT NOT NULL,
                    blob_path TEXT NOT NULL,
                    source_metadata_json TEXT NOT NULL,
                    validation_report_json TEXT NOT NULL,
                    UNIQUE(adapter_id, checksum)
                );
                CREATE TABLE IF NOT EXISTS records (
                    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
                    record_index INTEGER NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(dataset_id, record_index)
                );
                CREATE TABLE IF NOT EXISTS screening_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    dataset_ids_json TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS datasets_no_update
                BEFORE UPDATE ON datasets BEGIN SELECT RAISE(ABORT, 'dataset snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS datasets_no_delete
                BEFORE DELETE ON datasets BEGIN SELECT RAISE(ABORT, 'dataset snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS records_no_update
                BEFORE UPDATE ON records BEGIN SELECT RAISE(ABORT, 'dataset records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS records_no_delete
                BEFORE DELETE ON records BEGIN SELECT RAISE(ABORT, 'dataset records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS runs_no_update
                BEFORE UPDATE ON screening_runs BEGIN SELECT RAISE(ABORT, 'screening runs are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS runs_no_delete
                BEFORE DELETE ON screening_runs BEGIN SELECT RAISE(ABORT, 'screening runs are immutable'); END;
            """)

    def add_snapshot(
        self,
        *,
        adapter_id: str,
        raw_filename: str,
        payload: bytes,
        records: list[dict[str, Any]],
        source: SourceMetadata,
        validation_report: ValidationReport,
    ) -> DatasetSnapshot:
        actual_checksum = __import__("hashlib").sha256(payload).hexdigest()
        if actual_checksum != source.checksum:
            raise ValueError("Payload checksum does not match source metadata")
        if len(records) != source.record_count or validation_report.record_count != len(records):
            raise ValueError("Record counts do not agree")
        dataset_id = f"{adapter_id}:{source.checksum[:20]}"
        retrieval_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        suffix = Path(raw_filename).suffix.lower() or ".bin"
        blob_path = self.blob_dir / f"{source.checksum}{suffix}"
        if not blob_path.exists():
            blob_path.write_bytes(payload)

        with self._connect() as connection:
            existing = connection.execute("SELECT dataset_id FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
            if not existing:
                connection.execute(
                    """INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        dataset_id, adapter_id, retrieval_timestamp, source.effective_date,
                        source.dataset_version, source.checksum, source.record_count,
                        Path(raw_filename).name, str(blob_path.relative_to(self.root)),
                        json.dumps(source.to_dict(), sort_keys=True),
                        json.dumps(validation_report.to_dict(), sort_keys=True),
                    ),
                )
                connection.executemany(
                    "INSERT INTO records VALUES (?, ?, ?)",
                    [(dataset_id, index, json.dumps(record, sort_keys=True)) for index, record in enumerate(records)],
                )
        return self.get_snapshot(dataset_id)

    @staticmethod
    def _source(data: dict[str, Any]) -> SourceMetadata:
        data = dict(data)
        data["authoritative_status"] = AuthorityLevel(data["authoritative_status"])
        return SourceMetadata(**data)

    def get_snapshot(self, dataset_id: str) -> DatasetSnapshot:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown dataset snapshot: {dataset_id}")
        source = self._source(json.loads(row["source_metadata_json"]))
        return DatasetSnapshot(
            dataset_id=row["dataset_id"], source=source,
            retrieval_timestamp=row["retrieval_timestamp"], effective_date=row["effective_date"],
            version=row["version"], checksum=row["checksum"], record_count=row["record_count"],
            raw_filename=row["raw_filename"], validation_report=json.loads(row["validation_report_json"]),
        )

    def list_snapshots(self, adapter_id: str | None = None) -> list[DatasetSnapshot]:
        with self._connect() as connection:
            if adapter_id:
                rows = connection.execute("SELECT dataset_id FROM datasets WHERE adapter_id = ? ORDER BY retrieval_timestamp", (adapter_id,)).fetchall()
            else:
                rows = connection.execute("SELECT dataset_id FROM datasets ORDER BY retrieval_timestamp").fetchall()
        return [self.get_snapshot(row["dataset_id"]) for row in rows]

    def load_records(self, dataset_id: str) -> list[dict[str, Any]]:
        self.get_snapshot(dataset_id)
        with self._connect() as connection:
            rows = connection.execute("SELECT record_json FROM records WHERE dataset_id = ? ORDER BY record_index", (dataset_id,)).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def raw_snapshot_path(self, dataset_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute("SELECT blob_path FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown dataset snapshot: {dataset_id}")
        return self.root / row["blob_path"]

    def save_screening_run(self, run_id: str, dataset_ids: list[str], inputs: Any, results: Any) -> None:
        for dataset_id in dataset_ids:
            self.get_snapshot(dataset_id)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO screening_runs VALUES (?, ?, ?, ?, ?)",
                (
                    run_id, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    json.dumps(dataset_ids), json.dumps(inputs, sort_keys=True, default=str), json.dumps(results, sort_keys=True, default=str),
                ),
            )

    def load_screening_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM screening_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown screening run: {run_id}")
        return {
            "run_id": row["run_id"], "created_at": row["created_at"],
            "dataset_ids": json.loads(row["dataset_ids_json"]),
            "inputs": json.loads(row["input_json"]), "results": json.loads(row["result_json"]),
        }
