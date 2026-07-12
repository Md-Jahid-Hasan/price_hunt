from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import LLMQuerySerializer
from .services.router import handle_query, LLMRouterError


class LLMSearchView(APIView):
    def post(self, request):
        serializer = LLMQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = handle_query(serializer.validated_data["query"])
        except LLMRouterError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(result, status=status.HTTP_200_OK)