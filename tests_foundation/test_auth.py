import os,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from foundation.auth import OIDCVerifier

class TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    def test_signed_claims_and_rejections(self):
        with patch.dict(os.environ,{'OIDC_ISSUER':'https://identity.example.com','OIDC_AUDIENCE':'operator-api','OIDC_JWKS_URL':'https://identity.example.com/jwks'}):
            verifier=OIDCVerifier()
        claims={'sub':'alice','iss':'https://identity.example.com','aud':'operator-api','iat':int(time.time()),'exp':int(time.time())+120}
        with patch.object(verifier.keys,'get_signing_key_from_jwt',return_value=SimpleNamespace(key=self.key.public_key())):
            self.assertEqual(verifier(jwt.encode(claims,self.key,algorithm='RS256')).subject,'alice')
            bad=[{**claims,'exp':int(time.time())-60},{**claims,'iss':'https://attacker.example'},{**claims,'aud':'other-api'},{k:v for k,v in claims.items() if k!='exp'}]
            for item in bad:
                with self.assertRaises(HTTPException):verifier(jwt.encode(item,self.key,algorithm='RS256'))
            forged=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            with self.assertRaises(HTTPException):verifier(jwt.encode(claims,forged,algorithm='RS256'))
            with self.assertRaises(HTTPException):verifier(jwt.encode(claims,key='',algorithm='none'))
