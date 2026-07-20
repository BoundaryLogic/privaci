"""PII catalog sidecar models (parse-only; no row values)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sensitivity = Literal["pii_direct", "pii_indirect", "internal", "public"]
CatalogSource = Literal["pg_comment", "manual", "import"]


class PiiColumnEntry(BaseModel):
    """One annotated column in a PII catalog table entry."""

    model_config = ConfigDict(extra="forbid")

    name: str
    sensitivity: Sensitivity
    owner: str | None = None
    source: CatalogSource = "manual"
    notes: str | None = None


class PiiTableEntry(BaseModel):
    """Annotated columns for one schema-qualified table."""

    model_config = ConfigDict(extra="forbid")

    table: str
    columns: list[PiiColumnEntry] = Field(default_factory=list)


class PiiCatalog(BaseModel):
    """Root document for ``pii-catalog.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    catalog: list[PiiTableEntry] = Field(default_factory=list)
