import uuid

from django.conf import settings
from django.core.cache import cache

TTL: int = getattr(settings, "COMPARISON_TOKEN_TTL", 300)
_CACHE_PREFIX = "hist_token:"


class TokenValidationError(Exception):
    pass


def generate_comparison_token(product_ids: list[int]) -> str:
    """
    Store the allowed product IDs in Redis and return a single-use UUID token.
    The token expires after COMPARISON_TOKEN_TTL seconds.
    """
    token = str(uuid.uuid4())
    cache.set(_CACHE_PREFIX + token, sorted(set(product_ids)), timeout=TTL)
    return token


def validate_and_consume_token(token: str, requested_ids: list[int]) -> None:
    """
    Validate the token exists, hasn't expired, and that all requested_ids are
    within the set of IDs the token was issued for. Deletes the token on success
    (fetch all product history). Raises TokenValidationError with a descriptive message on failure.
    """
    if not token:
        raise TokenValidationError(
            "A valid history_token is required. Call the comparison endpoint first."
        )

    allowed_ids = cache.get(_CACHE_PREFIX + token)

    if allowed_ids is None:
        raise TokenValidationError(
            "Token not found or expired. Request a new comparison."
        )

    if not set(requested_ids).issubset(set(allowed_ids)):
        raise TokenValidationError(
            "Requested IDs are not covered by this token. "
            "Only IDs returned by the comparison can be queried."
        )
    else:
        # if requested ids is subset of allowed ids, then remove requested ids from allowed ids and update cache with remaining allowed ids
        remaining_ids = sorted(set(allowed_ids) - set(requested_ids))
        if remaining_ids:
            cache.set(_CACHE_PREFIX + token, remaining_ids, timeout=TTL)
        else:
            cache.delete(_CACHE_PREFIX + token)