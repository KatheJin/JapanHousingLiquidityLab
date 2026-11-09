"""Versioned PostgreSQL collection schema; original text and native query fields."""
from datetime import datetime
import json
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata=sa.MetaData()
LAYOUT={
'runs':'id source entry scope status started_at updated_at error',
'jobs':'run_id kind url listing_id state error',
'discovered':'source listing_id url first_seen_at last_discovered_at',
'pages':'run_id url observed_at sha256 detail_n next_url advertised_total',
'page_links':'run_id url listing_id',
'snapshots':'id run_id source listing_id observed_at success data raw error',
'batches':'id source listing_id body',
'events':'id source listing_id body',
'requests':'id run_id source url observed_at status elapsed_s error',
'controls':'source last_request_at'}
KEYS={'runs':['id'],'jobs':['run_id','kind','url'],'discovered':['source','listing_id'],
      'pages':['run_id','url'],'page_links':['run_id','url','listing_id'],'snapshots':['id'],
      'batches':['id'],'events':['id'],'requests':['id'],'controls':['source']}
TABLES={}
for name,layout in LAYOUT.items():
    cols=[]
    for c in layout.split():
        typ=sa.Integer if c in {'success','detail_n','advertised_total','status'} and not (name=='runs' and c=='status') else sa.Float if c in {'elapsed_s','last_request_at'} else sa.Text
        if name=='requests' and c=='id': cols.append(sa.Column(c,sa.BigInteger,sa.Identity(),primary_key=True));continue
        cols.append(sa.Column(c,typ,primary_key=c in KEYS[name]))
    cols.append(sa.Column('rowid',sa.BigInteger,sa.Identity(),nullable=False,unique=True))
    for c in layout.split():
        if c.endswith('_at'): cols.append(sa.Column(c+'_utc',sa.DateTime(timezone=True)))
    if name=='snapshots': cols += [sa.Column('attributes',JSONB),sa.Column('municipality',sa.Text),sa.Column('price_jpy',sa.Numeric(20,2))]
    if name in {'batches','events'}: cols.append(sa.Column('body_json',JSONB))
    if name=='events': cols.append(sa.Column('observation_id',sa.Text))
    TABLES[name]=sa.Table(name,metadata,*cols)
def fk(table,cols,target):
    TABLES[table].append_constraint(sa.ForeignKeyConstraint(cols,target,deferrable=True,initially='DEFERRED'))
for n in ['jobs','pages','page_links','snapshots','requests']: fk(n,['run_id'],['runs.id'])
fk('page_links',['run_id','url'],['pages.run_id','pages.url'])
fk('snapshots',['source','listing_id'],['discovered.source','discovered.listing_id'])
fk('batches',['id'],['snapshots.id']);fk('events',['observation_id'],['snapshots.id'])
sa.Index('ix_snap_source_id_time',TABLES['snapshots'].c.source,TABLES['snapshots'].c.listing_id,TABLES['snapshots'].c.observed_at_utc)
sa.Index('ix_snap_region_price',TABLES['snapshots'].c.municipality,TABLES['snapshots'].c.price_jpy)
sa.Index('ix_snap_observed',TABLES['snapshots'].c.observed_at_utc)
sa.Index('ix_jobs_pending',TABLES['jobs'].c.state,TABLES['jobs'].c.run_id)
for name in ['batches','events']: sa.Index('ix_'+name+'_source_id',TABLES[name].c.source,TABLES[name].c.listing_id)
sa.Table('collection_commands',metadata,sa.Column('id',sa.Text,primary_key=True),sa.Column('source',sa.Text),sa.Column('scope',sa.Text),sa.Column('action',sa.Text),sa.Column('status',sa.Text),sa.Column('requested_at',sa.DateTime(timezone=True)))
sa.Table('model_references',metadata,sa.Column('observation_id',sa.Text,sa.ForeignKey('snapshots.id'),primary_key=True),sa.Column('model_version',sa.Text,primary_key=True),sa.Column('predicted_at',sa.DateTime(timezone=True)),sa.Column('reference_quarter',sa.Text),sa.Column('result',JSONB))


def enriched(name,values):
    v=dict(values)
    for k,x in values.items():
        if k.endswith('_at') and isinstance(x,str): v[k+'_utc']=datetime.fromisoformat(x)
    if name=='snapshots' and v.get('data'):
        d=json.loads(v['data']);v.update(attributes=d,municipality=d.get('municipality'),price_jpy=d.get('price_jpy'))
    if name in {'batches','events'}: v['body_json']=json.loads(v['body'])
    if name=='events': v['observation_id']=v['id'].rsplit(':',1)[0]
    return v
