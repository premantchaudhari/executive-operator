"""Strict Gmail Message readback contract; no heuristic success detection."""
import base64
import hashlib
import re
from email.header import decode_header,make_header
from email.message import Message
from email.utils import getaddresses

CONTRACT='google.gmail.sent_plaintext.v1'

class SentMessageUnconfirmed(Exception):
    """A send returned an ID but its postcondition remains unconfirmed."""
    def __init__(self,mid):
        self.message_id=mid
        super().__init__('Sent message requires reconciliation')

def pointer_path(path):
    if not isinstance(path,str) or len(path)>512 or (path and not path.startswith('/')):
        raise ValueError('Reviewed response JSON pointer required')
    if re.search(r'~(?![01])',path):raise ValueError('Invalid response JSON pointer')
    return path

def project(data,path):
    for token in pointer_path(path).split('/')[1:]:
        key=token.replace('~1','/').replace('~0','~')
        if not isinstance(data,dict) or key not in data:raise ValueError('Provider response contract changed')
        data=data[key]
    return data

def message_id(data):
    value=data.get('id') if isinstance(data,dict) else None
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}',value):
        raise ValueError('Provider message ID required')
    return value

def verify_sent(plan,message,expected_id):
    if message_id(message)!=expected_id:raise ValueError('Readback message ID mismatch')
    labels=message.get('labelIds')
    if not isinstance(labels,list) or 'SENT' not in labels or 'DRAFT' in labels:
        raise ValueError('Sent mailbox state unconfirmed')
    payload=message.get('payload')
    if not isinstance(payload,dict) or payload.get('mimeType')!='text/plain' or payload.get('parts') or payload.get('filename'):
        raise ValueError('Only reviewed single-part plaintext is supported')
    raw_headers=payload.get('headers')
    if not isinstance(raw_headers,list) or len(raw_headers)>100:raise ValueError('Bounded headers required')
    headers={}
    for header in raw_headers:
        if not isinstance(header,dict) or not isinstance(header.get('name'),str) or not isinstance(header.get('value'),str):
            raise ValueError('Invalid readback header')
        headers.setdefault(header['name'].lower(),[]).append(header['value'])
    for name in ('to','subject'):
        if len(headers.get(name,[]))!=1:raise ValueError('Unique recipient and subject headers required')
    if any(any(v.strip() for v in headers.get(name,[])) for name in ('cc','bcc','resent-to','resent-cc','resent-bcc')):
        raise ValueError('Unexpected recipient headers')
    args=plan['arguments']
    recipients=getaddresses(headers['to'])
    if len(recipients)!=1 or recipients[0][1]!=args['recipient_email']:
        raise ValueError('Readback recipient mismatch')
    if str(make_header(decode_header(headers['subject'][0])))!=args['subject']:
        raise ValueError('Readback subject mismatch')
    if len(headers.get('content-type',[]))>1:raise ValueError('Duplicate content type')
    for value in headers.get('content-type',[]):
        mime=Message();mime['Content-Type']=value
        if mime.get_content_type()!='text/plain' or mime.get_content_charset() not in (None,'utf-8','us-ascii'):
            raise ValueError('Unsupported message charset')
    body=payload.get('body')
    if not isinstance(body,dict) or body.get('attachmentId'):raise ValueError('Inline plaintext body required')
    encoded=body.get('data')
    if not isinstance(encoded,str) or not re.fullmatch(r'[A-Za-z0-9_-]*={0,2}',encoded):
        raise ValueError('Invalid base64url body')
    decoded=base64.b64decode(encoded+'='*((-len(encoded))%4),altchars=b'-_',validate=True)
    if len(decoded)>64000:raise ValueError('Readback body exceeds cap')
    actual=decoded.decode('utf-8').replace('\r\n','\n')
    approved=args['body'].replace('\r\n','\n')
    # MIME serialization may add one terminal newline; no other edits allowed.
    if actual not in (approved,approved+'\n'):raise ValueError('Readback body mismatch')
    return {'verification':CONTRACT,'message_id':expected_id,'sent_copy_confirmed':True,
            'delivery_confirmed':False,'body_sha256':hashlib.sha256(approved.encode()).hexdigest()}
