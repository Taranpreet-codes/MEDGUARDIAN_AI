from rest_framework_simplejwt.authentication import JWTAuthentication

class QueryParamJWTAuthentication(JWTAuthentication):
    """
    Allows JWT authentication via the '?token=...' query parameter.
    Useful for authenticating browser EventSource connections which cannot set headers.
    """
    def get_raw_token(self, header):
        return None

    def authenticate(self, request):
        raw_token = request.query_params.get('token')
        if raw_token is None:
            return super().authenticate(request)
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
