from dataclasses import dataclass


@dataclass(frozen=True)
class ImportContext:
    source_name: str
    source_snapshot: str
