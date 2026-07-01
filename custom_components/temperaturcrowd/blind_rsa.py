import secrets
import hashlib

def _mgf1(mgf_seed: bytes, mask_len: int, hash_name: str = 'sha256') -> bytes:
    """Mask Generation Function MGF1."""
    T = b""
    h_func = hashlib.new(hash_name)
    hLen = h_func.digest_size
    for i in range((mask_len + hLen - 1) // hLen):
        C = i.to_bytes(4, "big")
        h = hashlib.new(hash_name)
        h.update(mgf_seed + C)
        T += h.digest()
    return T[:mask_len]

def _emsa_pss_encode(m: bytes, em_bits: int, salt: bytes = None, hash_name: str = 'sha256', sLen: int = 32) -> bytes:
    """
    EMSA-PSS-ENCODE (RFC 3447 / RFC 9474).
    """
    h_func = hashlib.new(hash_name)
    hLen = h_func.digest_size
    
    if salt is None:
        salt = secrets.token_bytes(sLen)
    else:
        sLen = len(salt)
        
    emLen = (em_bits + 7) // 8
    
    h_func.update(m)
    mHash = h_func.digest()
    
    M_prime = b"\x00" * 8 + mHash + salt
    H_func = hashlib.new(hash_name)
    H_func.update(M_prime)
    H = H_func.digest()
    
    PS = b"\x00" * (emLen - sLen - hLen - 2)
    DB = PS + b"\x01" + salt
    
    dbMask = _mgf1(H, emLen - hLen - 1, hash_name)
    
    maskedDB = bytes(a ^ b for a, b in zip(DB, dbMask))
    
    first_byte = maskedDB[0] & (0xFF >> (8 * emLen - em_bits))
    maskedDB = bytes([first_byte]) + maskedDB[1:]
    
    return maskedDB + H + b"\xbc"

def get_blinded_message(X: bytes, n_hex: str, e_hex: str) -> tuple[int, str]:
    """
    Blinds the secret X using the server's RSA public key (n, e) with RSASSA-PSS encoding.
    Returns (blinding_factor, blinded_message_hex).
    """
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    
    # 1. PSS encode the message
    em = _emsa_pss_encode(X, n.bit_length() - 1)
    m = int.from_bytes(em, 'big')
    
    # 2. Generate random blinding factor r (coprime to n)
    r = int.from_bytes(secrets.token_bytes(32), 'big')
    
    # 3. Blind: m' = m * r^e mod n
    blinded_m = (m * pow(r, e, n)) % n
    
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
