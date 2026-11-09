"""SQLAlchemy PostgreSQL repository reusing the tested Task010/collection logic."""
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from .pg_schema import TABLES,LAYOUT,KEYS,enriched
from .listing_pipeline import Store


def engine():
    url=os.environ.get('JHLL_DATABASE_URL','')
    if not url.startswith('postgresql+psycopg://'): raise ValueError('Set JHLL_DATABASE_URL; PostgreSQL is unavailable, no synthetic or SQLite fallback')
    return sa.create_engine(url,hide_parameters=True,pool_pre_ping=True)


class Row:
    def __init__(self,mapping): self.m={k:v.isoformat() if isinstance(v,datetime) else float(v) if isinstance(v,Decimal) else v for k,v in mapping.items()}
    def __getitem__(self,key): return list(self.m.values())[key] if isinstance(key,int) else self.m[key]
    def keys(self): return self.m.keys()
    def __iter__(self): return iter(self.m)


class Result:
    def __init__(self,result): self.result=result
    def fetchone(self):
        r=self.result.mappings().fetchone();return Row(r) if r is not None else None
    def __iter__(self): return (Row(r) for r in self.result.mappings())


class Connection:
    """Small legacy SQL bridge, not a new crawler or state-machine implementation."""
    def __init__(self,conn): self.conn=conn
    def __enter__(self): return self
    def __exit__(self,kind,*args):
        if kind: self.conn.rollback()
        else:
            try: self.conn.commit()
            except BaseException:
                self.conn.rollback();raise
    def execute(self,sql,params=()):
        match=re.fullmatch(r'INSERT( OR IGNORE| OR REPLACE)? INTO (\w+)(?:\(([^)]+)\))? VALUES\(([^)]+)\)(.*)',sql,re.I)
        if match:
            mode,name,cols,slots,tail=match.groups();table=TABLES[name]
            fields=[x.strip() for x in cols.split(',')] if cols else LAYOUT[name].split()
            if len(fields)!=len(params): raise ValueError('Legacy insert field count mismatch')
            values=enriched(name,dict(zip(fields,params)))
            if name=='jobs': values.setdefault('state','pending')
            q=insert(table).values(**values)
            if mode and 'IGNORE' in mode: q=q.on_conflict_do_nothing()
            elif mode or tail:
                updates={k:getattr(q.excluded,k) for k in values if k not in KEYS[name] and k!='rowid'}
                if tail: updates={k:getattr(q.excluded,k) for k in ['last_discovered_at','last_discovered_at_utc','url']}
                q=q.on_conflict_do_update(index_elements=KEYS[name],set_=updates)
            return Result(self.conn.execute(q))
        pieces=sql.split('?')
        if len(pieces)-1!=len(params): raise ValueError('SQL parameter count mismatch')
        statement=pieces[0]+''.join(':p'+str(i)+pieces[i+1] for i in range(len(params)))
        # Keep indexed native timestamps synchronized with original ISO text.
        statement=re.sub(r'\b(\w+_at)=(:p\d+)',lambda m:m[1]+'=CAST('+m[2]+' AS TEXT),'+m[1]+'_utc=CAST(CAST('+m[2]+' AS TEXT) AS TIMESTAMPTZ)',statement)
        return Result(self.conn.execute(sa.text(statement),{'p'+str(i):v for i,v in enumerate(params)}))


class PostgresStore(Store):
    # Session locks are released by PostgreSQL even after a killed worker.
    database_worker_lock=True
    def __init__(self,path=None):
        self.path=Path('data/postgres-runtime');self.path.mkdir(parents=True,exist_ok=True)
        self.engine=engine();self.connection=self.engine.connect()
        if not self.connection.execute(sa.text('SELECT pg_try_advisory_lock(12012001)')).scalar():
            self.connection.close();self.engine.dispose();raise ValueError('Central collection worker already active')
        self.connection.commit();self.db=Connection(self.connection)
    def record(self,run,source,lid,row,raw,error=None):
        parent=self.db.execute('SELECT source FROM runs WHERE id=?',(run,)).fetchone()
        if parent is None or parent['source']!=source: raise ValueError('Observation source does not match collection run')
        return super().record(run,source,lid,row,raw,error)
    def summary(self,source):
        result=super().summary(source);result['database']='PostgreSQL via JHLL_DATABASE_URL';result['backend']='postgresql';return result
    def close(self):
        self.connection.rollback();self.connection.execute(sa.text('SELECT pg_advisory_unlock(12012001)'));self.connection.commit();self.connection.close();self.engine.dispose()


class DataUnavailable(RuntimeError): pass


class ListingQuery:
    """Read-only service: no crawl trigger, separate from future administrator UI."""
    def _read(self,statement):
        try:e=engine()
        except ValueError:raise DataUnavailable('掲載データの接続設定を管理者に確認してください。') from None
        try:
            with e.connect() as c:
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                return [dict(Row(r)) for r in c.execute(statement).mappings()]
        except sa.exc.SQLAlchemyError:
            raise DataUnavailable('掲載データを読み込めません。時間をおいて再度お試しください。') from None
        finally:e.dispose()
    def history(self,source,listing_id,limit=1000):
        if not 1<=limit<=1000:raise ValueError('History limit 1..1000')
        t=TABLES['snapshots']
        return self._read(sa.select(t.c.id,t.c.observed_at,t.c.success,t.c.attributes,t.c.error).where(t.c.source==source,t.c.listing_id==listing_id).order_by(t.c.rowid.desc()).limit(limit))
    def coverage(self,source):
        t=TABLES['runs']
        return self._read(sa.select(t.c.id,t.c.source,t.c.entry,t.c.status,t.c.started_at,t.c.updated_at,t.c.error).where(t.c.source==source).order_by(t.c.rowid.desc()).limit(100))
    def search(self,source=None,municipality=None,min_price=0,max_price=1e15,limit=100):
        if not 1<=limit<=1000: raise ValueError('Query limit 1..1000')
        try:e=engine()
        except ValueError:raise DataUnavailable('掲載データを読み込めません。管理者に接続設定の確認を依頼してください。') from None
        s=TABLES['snapshots'];t=s.alias('t')
        q=sa.select(s).where(s.c.success==1,s.c.rowid==sa.select(sa.func.max(t.c.rowid)).where(t.c.source==s.c.source,t.c.listing_id==s.c.listing_id,t.c.success==1).scalar_subquery(),s.c.price_jpy.between(min_price,max_price))
        if source: q=q.where(s.c.source==source)
        if municipality: q=q.where(s.c.municipality==municipality)
        try:
            with e.connect().execution_options(isolation_level='REPEATABLE READ') as c:
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                rows=c.execute(q.order_by(s.c.observed_at_utc.desc()).limit(limit)).mappings()
                out=[]
                for r in rows:
                    last=c.execute(sa.select(s.c.success,s.c.observed_at).where(s.c.source==r['source'],s.c.listing_id==r['listing_id']).order_by(s.c.rowid.desc()).limit(1)).first()
                    ev=TABLES['events']
                    uncertain=c.execute(sa.select(ev.c.id).where(ev.c.source==r['source'],ev.c.listing_id==r['listing_id'],ev.c.body_json['kind'].astext=='identity_review_required').limit(1)).first()
                    state='unknown_identity' if uncertain else 'presence_observed' if last.success else 'unknown_coverage'
                    out.append(dict(source=r['source'],listing_id=r['listing_id'],last_confirmed_at=r['observed_at'],last_checked_at=last.observed_at,state=state,attributes=r['attributes'],evidence='Last confirmed historical listing observation; not guaranteed current inventory'))
                return out
        except sa.exc.SQLAlchemyError:
            raise DataUnavailable('掲載データベースに接続できません。時間をおいて再度お試しください。') from None
        finally:e.dispose()
