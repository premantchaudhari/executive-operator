import os
from dataclasses import dataclass
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException

@dataclass(frozen=True)
class Principal:
    subject: str

class OIDCVerifier:
    def __init__(self):
        self.issuer=os.environ['OIDC_ISSUER']
        self.audience=os.environ['OIDC_AUDIENCE']
        jwks=os.environ['OIDC_JWKS_URL']
        if not self.issuer.startswith('https://') or not jwks.startswith('https://'):
            raise ValueError('OIDC endpoints require HTTPS')
        self.keys=PyJWKClient(jwks,timeout=5,cache_keys=False)
    def __call__(self,token):
        try:
            key=self.keys.get_signing_key_from_jwt(token)
            claims=jwt.decode(token,key.key,algorithms=['RS256'],audience=self.audience,
                issuer=self.issuer,options={'require':['exp','iat','sub','iss','aud']})
            subject=claims['sub']
            if not isinstance(subject,str) or not 1<=len(subject)<=255: raise ValueError()
            return Principal(subject)
        except Exception:
            raise HTTPException(401,'Invalid or expired access token') from None
