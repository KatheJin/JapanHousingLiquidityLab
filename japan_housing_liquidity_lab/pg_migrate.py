"""Back up SQLite, migrate transactionally, compare exact legacy values, gate cutover."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from alembic import command
from alembic.config import Config
from .pg_schema import LAYOUT,TABLES,KEYS,enriched,metadata
from .pg_store import engine


def upgrade():
    config=Config('alembic.ini');command.upgrade(config,'head')


def migrate(source,backup_dir,activate=False):
    source=Path(source).resolve()
    if not source.is_file():raise ValueError('SQLite source does not exist')
    lock=Path(str(source)+'.collector.lock')
    try:lock.touch(exist_ok=False)
    except FileExistsError:raise ValueError('Stop SQLite collector before migrating') from None
    try:return _migrate(source,backup_dir,activate)
    finally:lock.unlink()


def _migrate(source,backup_dir,activate=False):
    source=Path(source).resolve();backup_dir=Path(backup_dir);backup_dir.mkdir(parents=True,exist_ok=True)
    origin=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);origin.row_factory=sqlite3.Row
    backup=backup_dir/('listings-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.sqlite3')
    destination=sqlite3.connect(backup);origin.backup(destination);destination.close();origin.close()
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    db=sqlite3.connect(backup);db.row_factory=sqlite3.Row
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('SQLite integrity failed')
    upgrade();e=engine();counts={};digests={}
    try:
        with e.begin() as conn:
            conn.execute(sa.text('SELECT pg_advisory_xact_lock(12012001)'))
            receipt=conn.execute(sa.select(metadata.tables['migration_receipts']).where(metadata.tables['migration_receipts'].c.source_sha256==source_hash)).first()
            for name,layout in LAYOUT.items():
                table=TABLES[name];rows=[dict(r) for r in db.execute('SELECT rowid AS _order,* FROM '+name+' ORDER BY rowid')]
                for row in rows:
                    order=row.pop('_order');values=enriched(name,row);values['rowid']=order
                    conn.execute(insert(table).values(**values).on_conflict_do_nothing(index_elements=KEYS[name]))
                expected=[dict(r) for r in db.execute('SELECT '+','.join(layout.split())+' FROM '+name+' ORDER BY rowid')]
                actual=[{k:r[k] for k in layout.split()} for r in conn.execute(sa.select(table).order_by(table.c.rowid)).mappings()]
                # Target may grow after cutover: all source keys must still match.
                lookup={tuple(r[k] for k in KEYS[name]):r for r in actual}
                for row in expected:
                    if (not receipt or name in {'snapshots','batches','events','requests','page_links'}) and lookup.get(tuple(row[k] for k in KEYS[name]))!=row: raise ValueError('Migration value mismatch: '+name)
                for r in conn.execute(sa.select(table)).mappings():
                    for k in layout.split():
                        if k.endswith('_at') and isinstance(r[k],str) and r[k] and r[k+'_utc']!=datetime.fromisoformat(r[k]): raise ValueError('Timestamp precision mismatch')
                counts[name]=dict(sqlite=len(expected),postgres=len(actual));digests[name]=hashlib.sha256(json.dumps(expected,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                for col in ['rowid']+(['id'] if name=='requests' else []):
                    conn.execute(sa.text(f"SELECT setval(pg_get_serial_sequence('{name}','{col}'), COALESCE((SELECT MAX({col}) FROM {name}),0)+1,false)"))
            cross_checks=[
                'SELECT COUNT(*) FROM snapshots s JOIN runs r ON s.run_id=r.id WHERE s.source<>r.source',
                'SELECT COUNT(*) FROM batches b JOIN snapshots s ON b.id=s.id WHERE b.source<>s.source OR b.listing_id<>s.listing_id',
                'SELECT COUNT(*) FROM events e JOIN snapshots s ON e.observation_id=s.id WHERE e.source<>s.source OR e.listing_id<>s.listing_id']
            if any(conn.execute(sa.text(q)).scalar() for q in cross_checks):raise ValueError('Migration source relationship mismatch')
            conn.execute(sa.text('SET CONSTRAINTS ALL IMMEDIATE'))
            conn.execute(insert(metadata.tables['migration_receipts']).values(source_sha256=source_hash,verified_at=datetime.now(timezone.utc),report=dict(counts=counts,digests=digests)).on_conflict_do_nothing())
        if hashlib.sha256(source.read_bytes()).hexdigest()!=source_hash: raise ValueError('Source changed during migration; do not cut over')
        result=dict(backup=str(backup.resolve()),backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),source_sha256=source_hash,counts=counts,source_row_digests=digests,exact_fields_verified=True,timestamps_verified=True,foreign_keys_verified=True,activated=activate)
        if activate:
            p=Path('data/postgres-runtime/active.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(backend='postgresql',source=str(source),verified_source_sha256=source_hash)),encoding='utf-8')
        report=backup.with_suffix('.report.json');report.write_text(json.dumps(result,indent=2),encoding='utf-8');return result
    finally: db.close();e.dispose()


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('data/listing-extension/listings.sqlite3'));p.add_argument('--backup-dir',type=Path,default=Path('data/postgres-backups'));p.add_argument('--activate',action='store_true');a=p.parse_args();print(json.dumps(migrate(a.source,a.backup_dir,a.activate)))

if __name__=='__main__':main()
