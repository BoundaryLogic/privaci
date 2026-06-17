"""Resolve aws-sm:// secret URIs via AWS Secrets Manager."""

from __future__ import annotations

import json
import logging
from typing import Any

from privaci.errors import SecretError
from privaci.secrets.backends.constants import CONNECT_TIMEOUT_S, READ_TIMEOUT_S
from privaci.secrets.parser import ParsedSecretUri

logger = logging.getLogger(__name__)


def resolve_aws_sm_uri(parsed: ParsedSecretUri) -> str:
    """Fetch a secret from AWS Secrets Manager.

    Args:
        parsed: Parsed aws-sm:// URI with optional region, key, version query params.

    Returns:
        Resolved secret string (or JSON field when ``key`` is set).

    Raises:
        SecretError: If boto3 is missing or the AWS API call fails.
    """
    client, region = _create_sm_client(parsed)
    try:
        payload = _fetch_secret_string(client, parsed, region=region)
    finally:
        client.close()
    return _extract_sm_payload(parsed, payload)


def _create_sm_client(parsed: ParsedSecretUri) -> tuple[Any, str | None]:
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError as exc:
        msg = "aws-sm:// requires the boto3 package"
        raise SecretError(msg) from exc

    query = parsed.query_dict()
    region = query.get("region")
    client_kwargs: dict[str, str] = {}
    if region:
        client_kwargs["region_name"] = region
    client = boto3.client(
        "secretsmanager",
        config=BotoConfig(
            connect_timeout=CONNECT_TIMEOUT_S,
            read_timeout=READ_TIMEOUT_S,
        ),
        **client_kwargs,
    )
    return client, region


def _fetch_secret_string(
    client: Any,
    parsed: ParsedSecretUri,
    *,
    region: str | None,
) -> str:
    from botocore.exceptions import BotoCoreError, ClientError

    query = parsed.query_dict()
    request: dict[str, Any] = {"SecretId": parsed.secret_id}
    version = query.get("version")
    if version:
        request["VersionId"] = version
    try:
        response = client.get_secret_value(**request)
    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "AWS Secrets Manager resolution failed",
            extra={"secret_id": parsed.secret_id, "region": region},
        )
        msg = f"Failed to resolve aws-sm://{parsed.secret_id}"
        raise SecretError(msg) from exc
    payload = response.get("SecretString")
    if payload is None:
        msg = f"aws-sm://{parsed.secret_id} has no SecretString payload"
        raise SecretError(msg)
    return str(payload).strip()


def _extract_sm_payload(parsed: ParsedSecretUri, payload: str) -> str:
    json_key = parsed.query_dict().get("key")
    if not json_key:
        return payload
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        msg = f"aws-sm://{parsed.secret_id} SecretString is not valid JSON"
        raise SecretError(msg) from exc
    if json_key not in data:
        msg = f"aws-sm://{parsed.secret_id} JSON key {json_key!r} not found"
        raise SecretError(msg)
    field = data[json_key]
    if not isinstance(field, str):
        msg = f"aws-sm://{parsed.secret_id} key {json_key!r} is not a string"
        raise SecretError(msg)
    return field.strip()
