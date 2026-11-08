"""Provider-independent contracts. Tool slugs/versions are never model-selected."""
TOOLS={
 'gmail.read':('gmail','read',('query',)),
 'gmail.get':('gmail','read',('message_id',)),
 'gmail.send':('gmail','write',('recipient_email','subject','body')),
 'calendar.read':('googlecalendar','read',('calendar_id','time_min','time_max')),
 'calendar.create':('googlecalendar','write',('calendar_id','title','start','end','timezone')),
 'calendar.cancel':('googlecalendar','write',('event_id',)),
 'drive.search':('googledrive','read',('query',)),
 'drive.read':('googledrive','read',('file_id',)),
 'sheets.read':('googlesheets','read',('spreadsheet_id','range')),
 'sheets.append':('googlesheets','write',('spreadsheet_id','range','values_json')),
 'slack.search':('slack','read',('query',)),
 'slack.send':('slack','write',('channel_id','text')),
 'hubspot.search':('hubspot','read',('query',)),
 'hubspot.create_contact':('hubspot','write',('email','firstname','lastname')),
 'quickbooks.query':('quickbooks','read',('query',)),
}
APPS=sorted({s[0] for s in TOOLS.values()})

def catalog():
    return [{'action':action,'app':app,'effect':effect,'fields':list(fields),'approval_required':effect=='write'} for action,(app,effect,fields) in TOOLS.items()]

def check_arguments(action,args):
    import json
    from datetime import datetime
    app,effect,fields=TOOLS[action]
    if set(args)!=set(fields) or any(not isinstance(v,str) or not v.strip() or len(v)>20000 for v in args.values()):raise ValueError('Invalid native tool arguments')
    if action=='gmail.get':
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,255}',args['message_id']):raise ValueError('Invalid Gmail message ID')
    if action=='sheets.append':
        rows=json.loads(args['values_json'])
        if not isinstance(rows,list) or not 1<=len(rows)<=1000 or any(not isinstance(r,list) or len(r)>100 or any(type(v) not in (str,int,float,bool,type(None)) for v in r) for r in rows):raise ValueError('Expected bounded JSON rows')
    if action.startswith('calendar.') and 'start' in args:
        start=datetime.fromisoformat(args['start']);end=datetime.fromisoformat(args['end'])
        if start.tzinfo is None or end.tzinfo is None or end<=start:raise ValueError('Calendar timestamps require offsets and end after start')
    if action=='quickbooks.query':
        # Only a conservative single SELECT form; mutating accounting tools remain unregistered.
        import re
        if not re.fullmatch(r'SELECT\s+[A-Za-z0-9_*, .]+\s+FROM\s+[A-Za-z][A-Za-z0-9_]*(?:\s+WHERE\s+[A-Za-z0-9_ =\'<>.-]+)?',args['query'],re.I):raise ValueError('Only a restricted read-only SELECT is supported')
