from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters.echa_candidate_list import ECHACandidateListAdapter
from .adapters.echa_annex_xvii import ECHAAnnexXVIIAdapter
from .adapters.eurlex_annex_xvii import EURLexAnnexXVIIReferenceAdapter
from .adapters.echa_clp_annex_vi import ECHACLPAnnexVIAdapter
from .adapters.eurlex_clp_annex_vi import EURLexCLPAnnexVIAdapter
from .store import DatasetStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChemReg Intel regulatory snapshot manager")
    parser.add_argument("--store", default="data/regulatory", help="Private local snapshot store")
    commands = parser.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser("import-candidate-list")
    import_command.add_argument("file")
    import_command.add_argument("--retrieval-date", required=True)
    import_command.add_argument("--effective-date")
    import_command.add_argument("--version")
    for command_name in ("import-annex-xvii", "import-annex-xvii-legal", "import-clp-annex-vi", "import-clp-annex-vi-legal"):
        command = commands.add_parser(command_name)
        command.add_argument("file")
        command.add_argument("--retrieval-date", required=True)
        command.add_argument("--effective-date")
        command.add_argument("--version")
    commands.add_parser("list")
    update = commands.add_parser("check-update")
    update.add_argument("dataset_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = DatasetStore(args.store)
    adapters = {
        "import-candidate-list": ECHACandidateListAdapter(),
        "import-annex-xvii": ECHAAnnexXVIIAdapter(),
        "import-annex-xvii-legal": EURLexAnnexXVIIReferenceAdapter(),
        "import-clp-annex-vi": ECHACLPAnnexVIAdapter(),
        "import-clp-annex-vi-legal": EURLexCLPAnnexVIAdapter(),
    }
    if args.command in adapters:
        adapter = adapters[args.command]
        path = Path(args.file)
        payload, records, source, report = adapter.import_file(
            path, retrieval_date=args.retrieval_date,
            effective_date=args.effective_date, dataset_version=args.version,
        )
        snapshot = store.add_snapshot(
            adapter_id=adapter.adapter_id, raw_filename=path.name, payload=payload,
            records=records, source=source, validation_report=report,
        )
        print(json.dumps({"dataset_id": snapshot.dataset_id, "version": snapshot.version, "record_count": snapshot.record_count, "checksum": snapshot.checksum}, indent=2))
    elif args.command == "list":
        print(json.dumps([{"dataset_id": item.dataset_id, "version": item.version, "record_count": item.record_count, "effective_date": item.effective_date} for item in store.list_snapshots()], indent=2))
    else:
        snapshot = store.get_snapshot(args.dataset_id)
        adapter_id = snapshot.dataset_id.split(":", 1)[0]
        adapter_by_id = {adapter.adapter_id: adapter for adapter in adapters.values()}
        if adapter_id not in adapter_by_id:
            raise ValueError(f"No update checker is registered for adapter {adapter_id}")
        adapter = adapter_by_id[adapter_id]
        report = adapter.check_for_update(snapshot.source)
        print(json.dumps({"status": report.status, "checked_at": report.checked_at, "message": report.message}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
