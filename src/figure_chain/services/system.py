from __future__ import annotations

from figure_chain.schemas import (
    SystemDependencyStatusResponse,
    SystemDiagnosticsResponse,
)
from figure_data.runtime.diagnostics import RuntimeDiagnostics


class SystemService:
    def __init__(self, diagnostics: RuntimeDiagnostics) -> None:
        self._diagnostics = diagnostics

    def diagnostics(self) -> SystemDiagnosticsResponse:
        return SystemDiagnosticsResponse(
            status=self._diagnostics.status,
            dependencies={
                item.name: SystemDependencyStatusResponse(
                    status=item.status,
                    message=item.message,
                )
                for item in self._diagnostics.dependencies
            },
            config=self._diagnostics.config,
        )
