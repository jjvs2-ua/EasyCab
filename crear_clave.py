from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.hashes import SHA256

# Generar clave privada RSA
clave_privada = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

# Guardar clave privada en un archivo
with open("clave_privada_taxi.pem", "wb") as archivo_privada:
    archivo_privada.write(
        clave_privada.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    )

# Generar clave pública RSA
clave_publica = clave_privada.public_key()

# Guardar clave pública en un archivo
with open("clave_publica_taxi.pem", "wb") as archivo_publica:
    archivo_publica.write(
        clave_publica.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )

print("Claves RSA generadas y guardadas en 'clave_privada_taxi.pem' y 'clave_publica_taxi.pem'")
