import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../custom_components/temperaturcrowd')))
import blind_rsa

class TestBlindRsaRFC9474(unittest.TestCase):
    def test_emsa_pss_encode_kat(self):
        # RFC 9474 A.1. RSABSSA-SHA384-PSS-Randomized Test Vector
        
        n_hex = (
            "aec4d69addc70b990ea66a5e70603b6fee27aafebd08f2d94cbe1250c556e047"
            "a928d635c3f45ee9b66d1bc628a03bac9b7c3f416fe20dabea8f3d7b4bbf7f963be3"
            "35d2328d67e6c13ee4a8f955e05a3283720d3e1f139c38e43e0338ad058a9495c533"
            "77fc35be64d208f89b4aa721bf7f7d3fef837be2a80e0f8adf0bcd1eec5bb040443a"
            "2b2792fdca522a7472aed74f31a1ebe1eebc1f408660a0543dfe2a850f106a617ec6"
            "685573702eaaa21a5640a5dcaf9b74e397fa3af18a2f1b7c03ba91a6336158de420d"
            "63188ee143866ee415735d155b7c2d854d795b7bc236cffd71542df34234221a0413"
            "e142d8c61355cc44d45bda94204974557ac2704cd8b593f035a5724b1adf442e78c5"
            "42cd4414fce6f1298182fb6d8e53cef1adfd2e90e1e4deec52999bdc6c29144e8d52"
            "a125232c8c6d75c706ea3cc06841c7bda33568c63a6c03817f722b50fcf898237d78"
            "8a4400869e44d90a3020923dc646388abcc914315215fcd1bae11b1c751fd52443aa"
            "c8f601087d8d42737c18a3fa11ecd4131ecae017ae0a14acfc4ef85b83c19fed33cf"
            "d1cd629da2c4c09e222b398e18d822f77bb378dea3cb360b605e5aa58b20edc29d00"
            "0a66bd177c682a17e7eb12a63ef7c2e4183e0d898f3d6bf567ba8ae84f84f1d23bf8"
            "b8e261c3729e2fa6d07b832e07cddd1d14f55325c6f924267957121902dc19b3b329"
            "48bdead5"
        )
        n = int(n_hex, 16)
        
        # The randomized variants prepend msg_prefix to msg. The RFC 9474 test vector provides "prepared_msg" which is the concatenation of both.
        prepared_msg_hex = (
            "8417e699b219d583fb6216ae0c53ca0e9723442d02f1d1a342955"
            "27e7d929e8b8f3dc6fb8c4a02f4d6352edf0907822c1210a9b32f9bdda4c45a698c8"
            "0023aa6b59f8cfec5fdbb36331372ebefedae7d"
        )
        prepared_msg = bytes.fromhex(prepared_msg_hex)
        
        salt_hex = (
            "051722b35f458781397c3a671a7d3bd3096503940e4c4f1aaa269d60300ce"
            "449555cd7340100df9d46944c5356825abf"
        )
        salt = bytes.fromhex(salt_hex)
        
        expected_encoded_msg_hex = (
            "2be01c5669eb676cb3f0002eb636427d61568f3f0579da5b998279"
            "a7eb3ab784e5617319376d04809d83e72bef9f0738e7324af3fd1b4f0a35f4f58058"
            "ab329495406bdb5ff31a0274be2d137c735ab0d5a591b3129a6cc46fcecc4b41dbc6"
            "84c965cb30e3eb4864ef18cc8d95b4d6a2002607c821d4d8a7e026ae7bb1f6b4c7c9"
            "3d1b58e9cd87864d6094b0d8f7e2b5f966473703634fb58c774dd4a24376e0eb262a"
            "24b58e3a0b4da4f36ef75651627561ff2ecee9dcbfe1d728cc31a7b46030f7a2815a"
            "e9edf9a2a5c0c6d8dbab1b33b9c3bbda5c083670a3550f7d74c4263aad09f8ed1d43"
            "5fc6295ca4d51fc02c7de9ae28ffd53372c3fa864521b27560daa11ab9daad8d0d74"
            "7661718d2f79c59d0661b09c74863fa32bdcb1c408d3bd24569c57aecae6e06c0c9d"
            "eb7303c5b7b1240960fd2413d61b2e3829af8c09874fdba0fe84ca6aa7e7d533f9b0"
            "ddfe508f562b132ca2d325f1e73f91a8a6b831a2fd9bc0bd5bfa5ea3a1dee16bd9b2"
            "64174b9553a4c0c0d62373353355c05b35824e4bae702f49e5a6bf83eaff65af4990"
            "45bcef1470a0e58ddb21856034af0db96f8636d4a6f1591f34c7224e0c0293e3d3be"
            "2139f2797c5ed8b65473ac2f83c52b87f8cf8754ac2f55f5e41e105df1d079a647fb"
            "1aa591526295667f37db1129752d024eb03bfe506a43665072118423351ef9b86633"
            "76f9fc073141e1e7bc"
        )
        
        # Test encode
        encoded_msg = blind_rsa._emsa_pss_encode(
            m=prepared_msg,
            em_bits=n.bit_length() - 1,
            salt=salt,
            hash_name="sha384",
            sLen=len(salt)
        )
        
        self.assertEqual(encoded_msg.hex(), expected_encoded_msg_hex)

if __name__ == '__main__':
    unittest.main()
