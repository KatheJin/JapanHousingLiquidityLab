"""Local PostgreSQL operator commands. No credentials in command-line arguments."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import secrets
import subprocess
from sqlalchemy.engine import URL,make_url


def local_environment():
    if os.environ.get('JHLL_DATABASE_URL'): return
    secret=Path('.env.pg-local')
    password=os.environ.get('JHLL_PG_PASSWORD')
    if not password:
        if not secret.exists() and Path('data/postgres-local/cluster/PG_VERSION').exists():
            raise ValueError('Existing local cluster credentials are missing; supply environment credentials, do not reset automatically')
        if not secret.exists(): secret.write_text('JHLL_PG_PASSWORD='+secrets.token_hex(24)+'\n',encoding='utf-8')
        password=secret.read_text(encoding='utf-8').strip().split('=',1)[1]
    os.environ['JHLL_PG_PASSWORD']=password
    os.environ['JHLL_DATABASE_URL']=URL.create('postgresql+psycopg',username='jhll_owner',password=password,host='127.0.0.1',port=55432,database='jhll_listings').render_as_string(hide_password=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','stop','upgrade','migrate','collect','backup','restore']);p.add_argument('--bin',type=Path,default=Path('C:/posgresql/18/bin'));p.add_argument('--file',type=Path);p.add_argument('--database',help='Fresh database name for restore only');a,rest=p.parse_known_args()
    local_environment();u=make_url(os.environ['JHLL_DATABASE_URL'])
    if u.host not in {'127.0.0.1','localhost','::1'}:raise ValueError('This operator helper only manages local PostgreSQL')
    env=dict(os.environ,PGHOST=u.host or '127.0.0.1',PGPORT=str(u.port or 5432),PGUSER=u.username or '',PGPASSWORD=u.password or '',PGDATABASE=u.database or '')
    folder=Path('data/postgres-local');folder.mkdir(parents=True,exist_ok=True);cluster=folder/'cluster'
    def call(name,args,allow_failure=False):
        with (folder/'operator.log').open('ab') as log:
            result=subprocess.run([str(a.bin/(name+'.exe')),*map(str,args)],env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode and not allow_failure: raise ValueError('PostgreSQL operation failed; inspect ignored operator.log')
        return result.returncode
    if a.command=='start':
        if not (cluster/'PG_VERSION').exists():
            pw=folder/'bootstrap-password.txt';pw.write_text(u.password or '',encoding='utf-8')
            try: call('initdb',['-D',cluster,'-U',u.username,'-A','scram-sha-256','--pwfile',pw,'--encoding=UTF8','--locale=C'])
            finally:pw.unlink(missing_ok=True)
        if call('pg_isready',['-h',u.host,'-p',str(u.port)],True): call('pg_ctl',['-D',cluster,'-l',folder/'server.log','-o',f'-h 127.0.0.1 -p {u.port}','start'])
        call('createdb',[u.database],True)
    elif a.command=='stop': call('pg_ctl',['-D',cluster,'stop','-m','fast'])
    elif a.command=='upgrade':
        from .pg_migrate import upgrade
        upgrade()
    elif a.command=='migrate':
        from .pg_migrate import main as migrate
        import sys
        sys.argv=[sys.argv[0],*rest];migrate()
    elif a.command=='collect':
        from .listing_pipeline import main as collect
        import sys
        sys.argv=[sys.argv[0],'--backend','postgresql','collect',*rest];collect()
    elif a.command=='backup':
        target=a.file or Path('data/postgres-backups')/('pg-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.dump')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists(): raise ValueError('Use a new backup path')
        call('pg_dump',['-Fc','--file',target]);print('Backup:',target)
    else:
        if not a.file or not a.file.exists() or not a.database: raise ValueError('Restore requires --file and a fresh --database')
        if call('createdb',[a.database],True): raise ValueError('Restore target must be a new database; no overwrite allowed')
        call('pg_restore',['--single-transaction','--no-owner','--exit-on-error','--dbname',a.database,a.file])
    print('Local PostgreSQL operation completed; no deployment performed')

if __name__=='__main__':main()
