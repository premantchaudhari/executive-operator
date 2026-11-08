"""Opt-in HubSpot/Sheets postconditions; no generic HTTP-success verifier."""
import hashlib
import json
import re

CONTRACTS={
    'hubspot.create_contact':('hubspot.contact_properties.v1','hubspot.get_contact'),
    'sheets.append':('google.sheets.raw_append.v1','sheets.read'),
}

class WriteUnconfirmed(Exception):
    def __init__(self,evidence):
        self.evidence=evidence
        super().__init__('Write postcondition requires reconciliation')

def column(value):
    total=0
    for c in value:total=total*26+ord(c)-64
    if not 1<=total<=18278:raise ValueError('Column exceeds Sheets limits')
    return total

def column_name(value):
    output=''
    while value:
        value,remainder=divmod(value-1,26);output=chr(65+remainder)+output
    return output

def a1(value):
    if not isinstance(value,str) or len(value)>512:raise ValueError('Bounded explicit sheet range required')
    match=re.fullmatch(r"(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_ ]*))!([A-Z]+)([1-9][0-9]*)?(?::([A-Z]+)([1-9][0-9]*)?)?",value)
    if not match:raise ValueError('Explicit sheet and column interval required')
    quoted,sheet,c1,r1,c2,r2=match.groups()
    if c2 is None:c2,r2=c1,r1
    sheet=quoted.replace("''","'") if quoted is not None else sheet
    lo,hi=column(c1),column(c2);start=int(r1 or 1);end=int(r2) if r2 else None
    if lo>hi or (r1 is None)!=(r2 is None) or (end is not None and (end<start or end>10000000)):
        raise ValueError('Invalid range bounds')
    return sheet,lo,hi,start,end

def rows_for(plan):
    rows=json.loads(plan['arguments']['values_json'])
    if not rows or not rows[0] or any(len(row)!=len(rows[0]) or all(v in (None,'') for v in row) for row in rows):
        raise ValueError('Verification requires rectangular rows with a nonblank cell per row')
    if any(type(v)==int and abs(v)>9007199254740991 for row in rows for v in row):
        raise ValueError('Large numeric identifiers must be supplied as strings')
    return rows

def preflight(plan,definition,read_definition):
    if plan['action']=='sheets.append':
        if definition.get('defaults',{}).get('value_input_option')!='RAW':
            raise ValueError('Reviewed RAW append parameter required')
        if read_definition.get('defaults',{}).get('value_render_option')!='UNFORMATTED_VALUE':
            raise ValueError('Reviewed unformatted readback parameter required')
        if any(d.get('defaults',{}).get('major_dimension','ROWS')!='ROWS' for d in (definition,read_definition)):
            raise ValueError('Row-major append and readback required')
        if ':' not in plan['arguments']['range'].split('!')[-1]:raise ValueError('Explicit append column interval required')
        bounds=a1(plan['arguments']['range']);rows=rows_for(plan)
        if len(rows[0])>bounds[2]-bounds[1]+1:raise ValueError('Input exceeds approved columns')

def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def same_cell(a,b):
    if a in (None,'') and b in (None,''):return True
    if isinstance(a,bool) or isinstance(b,bool):return type(a)==type(b) and a==b
    if type(a) in (int,float) and type(b) in (int,float):return a==b
    return type(a)==type(b) and a==b

def verify_write(gateway,org,plan,account_id,data):
    action=plan['action'];args=plan['arguments']
    evidence={'verification':CONTRACTS[action][0],'action':action,'postcondition_confirmed':False}
    if action=='hubspot.create_contact':
        cid=data.get('id') if isinstance(data,dict) else None
        if not isinstance(cid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}',cid):
            raise WriteUnconfirmed(evidence)
        evidence['contact_id']=cid
        try:
            result=gateway.execute(org,{'action':'hubspot.get_contact','account_id':account_id,'arguments':{'contact_id':cid}})['data']
            if not isinstance(result,dict) or result.get('id')!=cid or result.get('archived') is not False:
                raise ValueError('Contact state mismatch')
            expected={k:args[k] for k in ('email','firstname','lastname')}
            if not isinstance(result.get('properties'),dict) or any(result['properties'].get(k)!=v for k,v in expected.items()):
                raise ValueError('Contact properties mismatch')
            evidence['properties_sha256']=checksum(expected)
        except Exception:raise WriteUnconfirmed(evidence) from None
    else:
        evidence['spreadsheet_id']=args['spreadsheet_id']
        try:
            if not isinstance(data,dict) or data.get('spreadsheetId')!=args['spreadsheet_id']:raise ValueError('Spreadsheet mismatch')
            updates=data['updates'];updated=updates['updatedRange'];actual=a1(updated);approved=a1(args['range']);rows=rows_for(plan)
            evidence['updated_range']=updated
            sheet,c1,c2,r1,r2=actual;end_col=c1+len(rows[0])-1
            if (sheet!=approved[0] or c1<approved[1] or c2>end_col or end_col>approved[2] or
                r2 is None or r2-r1+1!=len(rows) or r1<approved[3] or (approved[4] is not None and r2>approved[4])):
                raise ValueError('Append escaped approved range or changed dimensions')
            if type(updates.get('updatedRows'))!=int or updates['updatedRows']!=len(rows):raise ValueError('Appended row count mismatch')
            if updates.get('spreadsheetId',args['spreadsheet_id'])!=args['spreadsheet_id']:raise ValueError('Update spreadsheet mismatch')
            quoted="'"+sheet.replace("'","''")+"'"
            read_range=f'{quoted}!{column_name(c1)}{r1}:{column_name(end_col)}{r2}'
            evidence['readback_range']=read_range
            result=gateway.execute(org,{'action':'sheets.read','account_id':account_id,
                'arguments':{'spreadsheet_id':args['spreadsheet_id'],'range':read_range}})['data']
            if not isinstance(result,dict) or a1(result.get('range'))!=(sheet,c1,end_col,r1,r2) or result.get('majorDimension','ROWS')!='ROWS':
                raise ValueError('Readback range/dimension mismatch')
            values=result.get('values')
            if not isinstance(values,list) or len(values)!=len(rows):raise ValueError('Readback rows missing')
            for expected,row in zip(rows,values):
                if not isinstance(row,list) or len(row)>len(expected):raise ValueError('Unexpected readback columns')
                padded=row+['']*(len(expected)-len(row))
                if any(not same_cell(a,b) for a,b in zip(expected,padded)):raise ValueError('Readback cell mismatch')
            evidence['values_sha256']=checksum(rows)
        except Exception:raise WriteUnconfirmed(evidence) from None
    evidence['postcondition_confirmed']=True
    return evidence
