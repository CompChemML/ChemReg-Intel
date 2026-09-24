from __future__ import annotations

from datetime import datetime, timezone

from .metadata import UpdateReport, UpdateStatus


def evaluate_update(
    local_version: str,
    remote_version: str | None,
    *,
    source_available: bool = True,
    manual_update_required: bool = False,
    message: str = "",
) -> UpdateReport:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if manual_update_required:
        status = UpdateStatus.MANUAL_UPDATE_REQUIRED
    elif not source_available:
        status = UpdateStatus.SOURCE_UNAVAILABLE
    elif not remote_version:
        status = UpdateStatus.VERSION_UNKNOWN
    elif remote_version == local_version:
        status = UpdateStatus.CURRENT
    else:
        status = UpdateStatus.UPDATE_AVAILABLE
    return UpdateReport(status, now, local_version, remote_version, message)

