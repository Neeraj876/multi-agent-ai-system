import json
import logging
import os
from datetime import UTC, datetime, timedelta

from config.settings import (
    ADD_MAX_RESULTS,
    CONFIDENCE_THRESHOLD,
    MAX_RETRIES,
    OPENROUTER_API_KEY,
    SERPER_API_KEY,
)
from src.graph.research_graph import build_research_graph

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r. Using default %s.", name, value, default)
        return default


def _month_key_and_ttl() -> tuple[str, int]:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m"), int((now + timedelta(days=40)).timestamp())


def _safe_client_id(value: object) -> str:
    raw = str(value or "anonymous")
    cleaned = "".join(char for char in raw if char.isalnum() or char in {"-", "_"})
    return cleaned[:100] or "anonymous"


def _rate_limit_response(message: str) -> dict:
    return {
        "statusCode": 429,
        "body": {
            "final_report": "",
            "errors": [message],
        },
    }


def _check_rate_limit(event: dict) -> dict | None:
    if not _env_bool("RATE_LIMIT_ENABLED"):
        return None

    table_name = os.getenv("RATE_LIMIT_TABLE_NAME")
    if not table_name:
        logger.error("RATE_LIMIT_ENABLED=true but RATE_LIMIT_TABLE_NAME is missing.")
        return _rate_limit_response("Rate limiting is not configured on the server.")

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.exception("boto3 is required when RATE_LIMIT_ENABLED=true.")
        return _rate_limit_response("Rate limiting is not available on the server.")

    month_key, ttl = _month_key_and_ttl()
    client_id = _safe_client_id(event.get("client_id"))
    monthly_limit = _env_int("RATE_LIMIT_MONTHLY_LIMIT", 50)
    per_client_limit = _env_int("RATE_LIMIT_PER_CLIENT_LIMIT", 2)

    dynamodb = boto3.client("dynamodb")
    names = {"#count": "count", "#ttl": "ttl"}
    values = {
        ":zero": {"N": "0"},
        ":one": {"N": "1"},
        ":ttl": {"N": str(ttl)},
        ":monthly_limit": {"N": str(monthly_limit)},
        ":per_client_limit": {"N": str(per_client_limit)},
    }

    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": table_name,
                        "Key": {"pk": {"S": f"global#{month_key}"}},
                        "UpdateExpression": "SET #count = if_not_exists(#count, :zero) + :one, #ttl = :ttl",
                        "ConditionExpression": "attribute_not_exists(#count) OR #count < :monthly_limit",
                        "ExpressionAttributeNames": names,
                        "ExpressionAttributeValues": values,
                    }
                },
                {
                    "Update": {
                        "TableName": table_name,
                        "Key": {"pk": {"S": f"client#{client_id}#{month_key}"}},
                        "UpdateExpression": "SET #count = if_not_exists(#count, :zero) + :one, #ttl = :ttl",
                        "ConditionExpression": "attribute_not_exists(#count) OR #count < :per_client_limit",
                        "ExpressionAttributeNames": names,
                        "ExpressionAttributeValues": values,
                    }
                },
            ]
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "TransactionCanceledException":
            return _rate_limit_response("The public demo request limit has been reached.")
        logger.exception("DynamoDB rate-limit transaction failed.")
        return _rate_limit_response("Rate limiting failed on the server.")

    return None


def lambda_handler(event, context):
    # Log environment variables (masked for security)
    logger.info("SERPER_API_KEY present: %s", bool(os.getenv("SERPER_API_KEY")))
    logger.info("OPENROUTER_API_KEY present: %s", bool(os.getenv("OPENROUTER_API_KEY")))

    rate_limit_error = _check_rate_limit(event)
    if rate_limit_error:
        return rate_limit_error

    # Extract parameters from event with defaults
    query = event.get("query", "What are the benefits of using AWS Cloud Services?")
    confidence_threshold = event.get("confidence_threshold", CONFIDENCE_THRESHOLD)
    max_retries = event.get("max_retries", MAX_RETRIES)
    add_max_results = event.get("add_max_results", ADD_MAX_RESULTS)

    # Validate parameters
    if not 0 <= confidence_threshold <= 1:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Confidence threshold must be between 0 and 1"}),
        }
    if max_retries < 0:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Max retries must be non-negative"}),
        }
    if add_max_results < 1:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Additional max results must be positive"}),
        }

    # Build the research graph with custom parameters
    graph = build_research_graph(
        SERPER_API_KEY,
        OPENROUTER_API_KEY,
        confidence_threshold=confidence_threshold,
        max_retries=max_retries,
        add_max_results=add_max_results,
    )

    # Run the graph
    result = graph.invoke(
        {
            "query": query,
            "search_results": [],
            "summarized_content": "",
            "fact_checked_results": {},
            "final_report": "",
            "errors": [],
            "fact_check_attempts": 0,
            "summarization_attempts": 0,
            "max_results": 3,
            "search_retries": 0,
        }
    )

    return {
        "statusCode": 200,
        "body": {
            "final_report": result.get("final_report", ""),
            "errors": result.get("errors", []),
        },
    }
