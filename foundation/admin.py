"""Trusted local provisioning only; never an unauthenticated public bootstrap route."""
import argparse
from .database import database
from .models import Organization,Membership,Budget,identifier

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--owner-subject',required=True)
    p.add_argument('--budget-microusd',type=int,default=0)
    args=p.parse_args()
    if args.budget_microusd<0:raise SystemExit('Budget must be nonnegative')
    if not args.name.strip() or len(args.name)>160 or not 1<=len(args.owner_subject)<=255:raise SystemExit('Invalid name/subject')
    engine,sessions=database()
    try:
        with sessions.begin() as s:
            org=Organization(id=identifier(),name=args.name);s.add(org);s.flush()
            s.add(Budget(organization_id=org.id,limit_microusd=args.budget_microusd))
            s.add(Membership(organization_id=org.id,subject=args.owner_subject,role='owner'))
        print(org.id)
    finally:engine.dispose()
if __name__=='__main__':main()
