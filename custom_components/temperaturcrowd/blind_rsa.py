import secrets
import hashlib

def get_blinded_message(X: bytes, n_hex: str, e_hex: str) -> tuple[int, str]:
    """
    Blinds the secret X using the server's RSA public key (n, e).
    Returns (blinding_factor, blinded_message_hex).
    """
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    
    # 1. Hash X to get m
    m_bytes = hashlib.sha256(X).digest()
    m = int.from_bytes(m_bytes, 'big') % n
    
    # 2. Generate random blinding factor r (coprime to n)
    # n is a product of two large primes, so any random 256-bit number is coprime with overwhelming probability
    r = int.from_bytes(secrets.token_bytes(32), 'big')
    
    # 3. Blind: m' = m * r^e mod n
    blinded_m = (m * pow(r, e, n)) % n
    
    # Return r (for unblinding later) and the hex string of m'
    # We pad the hex string to match the modulus length in bytes
    modulus_bytes = (n.bit_length() + 7) // 8
    blinded_hex = blinded_m.to_bytes(modulus_bytes, 'big').hex()
    
    return r, blinded_hex

def unblind_signature(r: int, signed_blinded_hex: str, n_hex: str) -> str:
    """
    Unblinds the signature returned by the server.
    Returns the final signature as a hex string.
    """
    n = int(n_hex, 16)
    signed_blinded = int(signed_blinded_hex, 16)
    
    # 4. Unblind: s = s' * r^-1 mod n
    r_inv = pow(r, -1, n)
    signed_m = (signed_blinded * r_inv) % n
    
    modulus_bytes = (n.bit_length() + 7) // 8
    return signed_m.to_bytes(modulus_bytes, 'big').hex()
