import json
import logging
import os

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


def _parse_event(event):
    if isinstance(event, dict) and isinstance(event.get("body"), str):
        return json.loads(event["body"] or "{}"), True
    return event, False


def _response(status_code, body, is_api_gateway_event):
    if is_api_gateway_event:
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }
    return {"statusCode": status_code, "body": body}


def lambda_handler(event, context):
    event, is_api_gateway_event = _parse_event(event)

    # Log environment variables (masked for security)
    logger.info("SERPER_API_KEY present: %s", bool(os.getenv("SERPER_API_KEY")))
    logger.info("OPENROUTER_API_KEY present: %s", bool(os.getenv("OPENROUTER_API_KEY")))

    # Extract parameters from event with defaults
    query = event.get("query", "What are the benefits of using AWS Cloud Services?")
    confidence_threshold = event.get("confidence_threshold", CONFIDENCE_THRESHOLD)
    max_retries = event.get("max_retries", MAX_RETRIES)
    add_max_results = event.get("add_max_results", ADD_MAX_RESULTS)

    # Validate parameters
    if not 0 <= confidence_threshold <= 1:
        return _response(400, {"error": "Confidence threshold must be between 0 and 1"}, is_api_gateway_event)
    if max_retries < 0:
        return _response(400, {"error": "Max retries must be non-negative"}, is_api_gateway_event)
    if add_max_results < 1:
        return _response(400, {"error": "Additional max results must be positive"}, is_api_gateway_event)

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

    return _response(
        200,
        {
            "final_report": result.get("final_report", ""),
            "errors": result.get("errors", []),
        },
        is_api_gateway_event,
    )
