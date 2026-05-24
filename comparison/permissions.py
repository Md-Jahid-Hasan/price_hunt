from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

from .tokens import validate_and_consume_token, TokenValidationError


class ComparisonTokenPermission(BasePermission):
    """
    Requires a valid `history_token` query param that was issued by
    ProductComparisonView. The token is single-use and expires after
    settings.COMPARISON_TOKEN_TTL seconds.

    Also requires `ids` to be present so the token scope can be validated
    before the view body runs.
    """

    def has_permission(self, request, view) -> bool:
        token = request.query_params.get("history_token", "").strip()

        raw_ids = request.query_params.get("ids", "").strip()
        try:
            requested_ids = [int(x) for x in raw_ids.split(",") if x.strip()]
        except ValueError:
            raise PermissionDenied(
                "Cannot validate token: 'ids' parameter contains non-integer values."
            )

        try:
            validate_and_consume_token(token, requested_ids)
        except TokenValidationError as exc:
            raise PermissionDenied(str(exc))

        return True