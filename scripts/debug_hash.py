from passlib.context import CryptContext
try:
    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    hash = pwd_context.hash("admin")
    print(f"Hash success: {hash}")
except Exception as e:
    print(f"Hash failed: {e}")
