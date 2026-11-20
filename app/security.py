"""Utilidades de seguridad (solo libreria estandar):
- Hash de contrasenas con PBKDF2-SHA256
- Tokens firmados con HMAC para identificar al usuario y su rol
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

ITERACIONES = 200_000
PREFIJO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERACIONES).hex()
    return f"{PREFIJO}${ITERACIONES}${salt}${h}"


def esta_hasheada(valor: str) -> bool:
    return bool(valor) and valor.startswith(PREFIJO + "$")


def verificar_password(password: str, guardada: str) -> bool:
    # Compatibilidad: si en la BD aun hay texto plano (datos de prueba), se compara directo
    if not esta_hasheada(guardada):
        return hmac.compare_digest(password.encode(), guardada.encode())
    try:
        _, iteraciones, salt, h = guardada.split("$")
        calculado = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iteraciones)
        ).hex()
        return hmac.compare_digest(calculado, h)
    except ValueError:
        return False


def crear_token(datos: dict, secreto: str, duracion_seg: int = 8 * 3600) -> str:
    cuerpo = dict(datos, exp=int(time.time()) + duracion_seg)
    raw = base64.urlsafe_b64encode(json.dumps(cuerpo).encode()).decode().rstrip("=")
    firma = hmac.new(secreto.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{firma}"


def leer_token(token: str, secreto: str):
    """Devuelve el diccionario del token o None si es invalido/expirado."""
    try:
        raw, firma = token.split(".", 1)
        esperada = hmac.new(secreto.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, esperada):
            return None
        relleno = "=" * (-len(raw) % 4)
        datos = json.loads(base64.urlsafe_b64decode(raw + relleno))
        if datos.get("exp", 0) < time.time():
            return None
        return datos
    except Exception:
        return None
