from pydantic import BaseModel, Field


class AIFoundationDiagnosticOutput(BaseModel):
    message: str = Field(min_length=1)
    echo_id: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
