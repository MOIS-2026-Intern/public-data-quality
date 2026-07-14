from .remote_fetch import (
    append_query_params,
    decode_remote_text,
    fetch_remote,
    looks_like_html_response,
    normalize_http_url,
)
from .remote_payloads import classify_remote_payload, decompress_remote_payload, normalize_remote_text_payload

__all__ = [
    "append_query_params",
    "classify_remote_payload",
    "decode_remote_text",
    "decompress_remote_payload",
    "fetch_remote",
    "looks_like_html_response",
    "normalize_http_url",
    "normalize_remote_text_payload",
]
