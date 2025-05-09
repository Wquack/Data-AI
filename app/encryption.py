from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

KEY = get_random_bytes(32)  # 256-bit key

def encrypt_data(data):
    """Encrypt data using AES."""
    cipher = AES.new(KEY, AES.MODE_EAX)
    nonce = cipher.nonce
    ciphertext, tag = cipher.encrypt_and_digest(data.encode('utf-8'))
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_data(encrypted_data):
    """Decrypt data using AES."""
    raw = base64.b64decode(encrypted_data)
    nonce, ciphertext = raw[:16], raw[16:]
    cipher = AES.new(KEY, AES.MODE_EAX, nonce=nonce)
    return cipher.decrypt(ciphertext).decode('utf-8')