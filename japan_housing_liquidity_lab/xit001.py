"""Future official API boundary. Intentionally no HTTP client or key handling."""
from urllib.parse import urlencode

def request_url(year, quarter):
    if type(year) is not int or not 2023 <= year <= 9999:
        raise ValueError('Research scope starts in 2023')
    if type(quarter) is not int or quarter not in range(1,5):
        raise ValueError('quarter must be 1–4')
    return 'https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001?' + urlencode(
        dict(year=year,quarter=quarter,area='13',priceClassification='01',language='ja'))

def fetch(*args, **kwargs):
    raise NotImplementedError('Requires an approved official API key and a separately reviewed client')

def pending_quarters(published_quarters, acquired_quarters):
    """Plan only explicitly published quarters; absent data is not a zero count.

    A future approved provider supplies the publication inventory. This function
    does not infer release from the clock or an empty API response.
    """
    import re
    published = set(published_quarters)
    if any(not re.fullmatch(r'[0-9]{4}Q[1-4]',q) for q in published):
        raise ValueError('Invalid published quarter')
    return sorted(q for q in published-set(acquired_quarters) if q >= '2023Q1')
