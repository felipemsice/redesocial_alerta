import hmac
import os
from functools import wraps

from flask import Response, request


def protegido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        user, senha = os.getenv("DASHBOARD_USER", "admin"), os.getenv("DASHBOARD_PASSWORD", "")
        if not senha or not auth or not (
            hmac.compare_digest(auth.username or "", user) and hmac.compare_digest(auth.password or "", senha)
        ):
            return Response("Acesso restrito", 401, {"WWW-Authenticate": 'Basic realm="monitor"'})
        return f(*args, **kwargs)
    return wrapper
