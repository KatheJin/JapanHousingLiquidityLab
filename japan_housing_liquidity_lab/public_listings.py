"""Explicit-URL, local/private SUUMO pilot; no discovery or bulk collection."""
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
import uuid

import requests
from bs4 import BeautifulSoup
from protego import Protego

from . import listings
from .net_http import save

UA = 'JapanHousingLiquidityLab/0.1 (limited local private evaluation)'
TERMS = 'https://cdn.p.recruit.co.jp/terms/suu-t-1003/index.html'
TERMS_HASH = '0d1198b3cfef6eebcb2469b8e3546f02ee5a143375562e16afb99da90984cfa3'
REVIEW_DATE = '2026-11-09'
MAX_BYTES = 2_000_000


def terms_hash(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup(['script', 'style']):
        node.decompose()
    return hashlib.sha256(' '.join(soup.stripped_strings).encode()).hexdigest()


class StopCollection(ValueError):
    """A site or transport failure must stop the entire run, without retries."""


class Transport:
    def __init__(self):
        self.interval = 10.0
        self.last = None
        self.logs = []

    def get(self, url, media):
        if self.last is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        log = dict(url=url, status=None, bytes=0)
        self.logs.append(log)
        try:
            # No cookie jar, authentication, redirects, browser impersonation or retry.
            with requests.get(url, headers={'User-Agent': UA}, timeout=(10, 20),
                              allow_redirects=False, stream=True) as response:
                log['status'] = response.status_code
                if response.status_code != 200:
                    raise StopCollection('HTTP_' + str(response.status_code))
                if media not in response.headers.get('Content-Type', '').lower():
                    raise StopCollection('Unexpected_media_type')
                body = bytearray()
                for chunk in response.iter_content(16384):
                    body.extend(chunk)
                    log['bytes'] = len(body)
                    if len(body) > MAX_BYTES:
                        raise StopCollection('Response_too_large')
                    if time.monotonic() - self.last > 45:
                        raise StopCollection('Response_time_budget')
                html = body.decode('utf-8-sig')
                if re.search(r'<title[^>]*>[^<]*(captcha|access denied|just a moment|アクセス制限|認証)', html, re.I):
                    raise StopCollection('Access_challenge')
                return html
        except (requests.RequestException, UnicodeError) as exc:
            raise StopCollection(type(exc).__name__) from None


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))


def price_jpy(value):
    value = normalized(value).replace(',', '')
    match = re.fullmatch(r'(?:(\d+(?:\.\d+)?)億)?(?:(\d+(?:\.\d+)?)万)?円', value)
    if not match or not any(match.groups()):
        raise ValueError('Single explicit JPY asking price required')
    amount = Decimal(match[1] or '0') * 100_000_000 + Decimal(match[2] or '0') * 10_000
    if amount <= 0 or amount != int(amount):
        raise ValueError('Invalid asking price')
    return int(amount)


class SuumoAdapter:
    name = 'suumo-public-private-pilot'
    robots_url = 'https://suumo.jp/robots.txt'
    detail_pattern = re.compile(r'https://suumo\.jp/ms/chuko/[a-z]+/sc_[a-z]+/nc_(\d{8})/')

    def listing_id(self, url):
        match = self.detail_pattern.fullmatch(url)
        if not match:
            raise ValueError('Only canonical SUUMO used-condominium detail URLs are supported')
        return match[1]

    def parse(self, html, url):
        listing_id = self.listing_id(url)
        soup = BeautifulSoup(html, 'html.parser')
        if not soup.title or '中古マンション物件情報' not in soup.title.get_text():
            raise ValueError('Not a used-condominium detail page')
        canon = soup.select_one('link[rel="canonical"]')
        if canon and canon.get('href') != url:
            raise ValueError('Canonical identity mismatch')
        # Only whitelisted visible table facts; no photos, names, contacts or prose.
        wanted = {'価格', '専有面積', '完成時期(築年月)', '間取り'}
        fields = {key: [] for key in wanted}
        for header in soup.select('th'):
            label = header.select_one('.fl')
            key = normalized((label or header).get_text()).replace('ヒント', '')
            if key not in wanted:
                continue
            cell = header.find_next_sibling('td')
            if cell is None:
                raise ValueError('Missing table cell')
            # Remove controls, hidden text and scripts before reading visible values.
            for node in cell.select('script,style,input,select,button,[hidden],[style*="display:none"],[style*="display: none"]'):
                node.decompose()
            value = normalized(cell.get_text(' ', strip=True)).split('[')[0]
            fields[key].append(value)
        def unique(key, convert):
            values = {convert(v) for v in fields[key]}
            if len(values) != 1:
                raise ValueError('Missing or conflicting field: ' + key)
            return values.pop()
        def area(v):
            m = re.fullmatch(r'(\d+(?:\.\d+)?)(?:m2|m²|㎡)(?:\(.*\))*', v)
            if not m:
                raise ValueError('Ambiguous area')
            return float(m[1])
        def year(v):
            m = re.fullmatch(r'(\d{4})年(?:\d{1,2}月)?', v)
            if not m:
                raise ValueError('Ambiguous construction year')
            return int(m[1])
        def layout(v):
            if not re.fullmatch(r'\d{1,2}[A-Z]+(?:\+[A-Z]+)?', v):
                raise ValueError('Ambiguous layout')
            return v
        return dict(listing_id=listing_id, source_record_id=listing_id, url=url,
                    price_jpy=unique('価格', price_jpy), area_m2=unique('専有面積', area),
                    built_year=unique('完成時期(築年月)', year), layout=unique('間取り', layout),
                    status='present', evidence='Public detail table observed over HTTPS; asking price, not transaction price')


ADAPTERS = {'suumo': SuumoAdapter()}


def make_batch(adapter, urls, records, observed_at, errors):
    ids = sorted(adapter.listing_id(u) for u in urls)
    return dict(version=listings.VERSION, batch_id=str(uuid.uuid4()), source=adapter.name,
                scope_id='explicit-' + hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16],
                scope=dict(coverage_type='tracked_listing_ids', definition='Explicit URLs only; no absence inference', listing_ids=ids),
                observed_at=observed_at, completeness='partial' if records else 'failed',
                check_evidence='Limited positive-only pilot; HTTP errors/404/challenges never mean sale or withdrawal',
                data_kind='real', rights=dict(basis='public_terms_review',
                    evidence=f'SUUMO terms {TERMS}; reviewed {REVIEW_DATE}; local personal noncommercial evaluation only. '
                             'No open licence or separate provider permission claimed. No publication, redistribution or bulk research clearance.',
                    local_retention_allowed=True, url_retention_allowed=True), records=records)


def collect(source, urls, workspace, journal, *, local_private_only=False, transport=None):
    if not local_private_only:
        raise ValueError('This pilot is limited to local private noncommercial evaluation')
    adapter = ADAPTERS[source]
    if not 1 <= len(urls) <= 3 or len(set(urls)) != len(urls):
        raise ValueError('Supply 1 to 3 distinct explicit detail URLs; no discovery')
    ids = [adapter.listing_id(u) for u in urls]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate listing identity')
    now = datetime.now(timezone.utc)
    reviewed = datetime.fromisoformat(REVIEW_DATE).replace(tzinfo=timezone.utc)
    if not reviewed - timedelta(days=1) <= now <= reviewed + timedelta(days=7):
        raise ValueError('Source review expired; re-check terms and access before updating adapter')
    work = Path(workspace)
    work.mkdir(parents=True, exist_ok=True)
    lock = work / 'writer.lock'
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        raise ValueError('Collector locked; inspect interrupted run') from None
    try:
        pending = work / 'pending.json'
        if pending.exists():
            envelope = json.loads(pending.read_text(encoding='utf-8'))
            if envelope['journal'] != str(Path(journal).resolve()):
                raise ValueError('Pending journal destination mismatch')
            listings.ingest(Path(journal), envelope['batch'])
            pending.unlink()
        state = work / 'last-run.json'
        if state.exists():
            last = datetime.fromisoformat(json.loads(state.read_text(encoding='utf-8'))['attempted_at'])
            if now - last < timedelta(hours=24):
                raise ValueError('Local source cooldown: at most one pilot run per 24 hours')
        save(state, dict(attempted_at=now.isoformat()))
        client = transport or Transport()
        records, errors = [], []
        try:
            robot_text = client.get(adapter.robots_url, 'text/plain')
            robot = Protego.parse(robot_text)
            if not all(robot.can_fetch(url, UA) for url in urls):
                raise StopCollection('Robots_disallow')
            delay = robot.crawl_delay(UA)
            rate = robot.request_rate(UA)
            client.interval = max(client.interval, float(delay or 0), float(rate.seconds / rate.requests) if rate else 0)
            if client.interval > 60:
                raise StopCollection('Site_delay_exceeds_pilot_budget')
            if terms_hash(client.get(TERMS, 'text/html')) != TERMS_HASH:
                raise StopCollection('Terms_changed_review_required')
            for url in urls:
                html = client.get(url, 'text/html')
                record = adapter.parse(html, url)
                listings.validate(make_batch(adapter, urls, [record], now.isoformat(), []))
                records.append(record)
        except (StopCollection, ValueError) as exc:
            errors.append(str(exc))
        batch = make_batch(adapter, urls, records, now.isoformat(), errors)
        batch = listings.validate(batch)
        save(pending, dict(journal=str(Path(journal).resolve()), batch=batch))
        listings.ingest(Path(journal), batch)
        pending.unlink()
        result = dict(batch_id=batch['batch_id'], real_records=len(records), completeness=batch['completeness'],
                      errors=errors, requests=client.logs, observed_at=now.isoformat())
        save(work / (batch['batch_id'] + '-run.json'), result)
        return result
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=ADAPTERS, default='suumo')
    parser.add_argument('--url', action='append', required=True)
    parser.add_argument('--local-private-only', action='store_true')
    parser.add_argument('--journal', type=Path, default=Path('data/task012-public/journal.json'))
    args = parser.parse_args()
    # Fixed project location prevents accidental cooldown reset by changing output folders.
    workspace = Path(__file__).resolve().parent.parent / 'data/task012-public/collector'
    result = collect(args.source, args.url, workspace, args.journal, local_private_only=args.local_private_only)
    print(json.dumps(result, ensure_ascii=False))
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
