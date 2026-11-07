"""Consistent SQLite backup. Protect the destination as client data."""
import argparse
import os
import sqlite3
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('destination')
args=parser.parse_args()
source=Path(args.source).resolve(strict=True)
destination=Path(args.destination).resolve()
if source == destination or destination.exists():
    raise SystemExit('Destination must be a new, different file')
# Atomic exclusive creation avoids accidentally overwriting an existing backup.
fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.close(fd)
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(destination) as dst:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Backup integrity check failed')
print('Backup created and integrity checked')
