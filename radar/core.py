"""Conservative eligibility, time provenance and deduplication. No paid APIs."""
import hashlib
import html
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

UTC = timezone.utc

def now():
    return datetime.now(UTC).isoformat()

def clean(value):
    return re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', html.unescape(html.unescape(str(value or ''))))).strip()

def timestamp(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if d.tzinfo is None or len(str(value)) <= 10:
            return None  # Date-only and timezone-free values cannot prove hourly recency.
        return d.astimezone(UTC).isoformat()
    except (ValueError, TypeError):
        return None

def canonical_url(url):
    p = urlsplit(str(url))
    if p.scheme != 'https' or not p.netloc:
        return ''
    q = [(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith(('utm_', 'trk', 'source'))]
    return urlunsplit(('https',p.netloc.lower(),p.path.rstrip('/'),urlencode(sorted(q)),''))

ROLE = re.compile(r'\b(data\s+(engineer\w*|platform|architect\w*|integration)|ETL|ELT|snowflake|cortex|microsoft fabric|azure fabric|databricks|palantir|foundry|analytics engineer\w*|data warehouse|big data)\b', re.I)
C2C = r'(?:c2c|corp[\s-]*to[\s-]*corp|corporation[\s-]*to[\s-]*corporation)'
STATES = {'AL':'Alabama','AR':'Arkansas','CT':'Connecticut','DE':'Delaware','DC':'District of Columbia','FL':'Florida','GA':'Georgia','IA':'Iowa','IL':'Illinois','IN':'Indiana','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','MA':'Massachusetts','MD':'Maryland','ME':'Maine','MI':'Michigan','MN':'Minnesota','MO':'Missouri','MS':'Mississippi','NC':'North Carolina','ND':'North Dakota','NE':'Nebraska','NH':'New Hampshire','NJ':'New Jersey','NY':'New York','OH':'Ohio','OK':'Oklahoma','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','VA':'Virginia','VT':'Vermont','WI':'Wisconsin','WV':'West Virginia'}
CITIES = r'\b(new york|chicago|dallas|houston|austin|boston|atlanta|philadelphia|miami|tampa|charlotte|raleigh|detroit|columbus|pittsburgh|nashville|minneapolis|st\.? louis|indianapolis|jersey city|newark|washington,? dc)\b'

def region(location):
    s = clean(location)
    us = bool(re.search(r'\b(united states|usa|u\.s\.|us)\b', s, re.I))
    state = any(re.search(r'\b'+name+r'\b',s,re.I) or re.search(r'(?:,\s*|\bUS[- ])'+code+r'\b',s) or s==code for code,name in STATES.items())
    city = bool(re.search(CITIES,s,re.I))
    remote = bool(re.search(r'\bremote\b',s,re.I))
    if state or city: return 'Central / Eastern USA'
    if remote and us: return 'US remote'
    if remote and re.search(r'worldwide|anywhere|global',s,re.I): return 'Global remote — verify US eligibility'
    if remote and not re.search(r'canada|india|europe|emea|uk|germany|brazil|australia',s,re.I): return 'Remote — country unverified'
    return 'Outside target / unverified'

def classify(title, description, employment=''):
    s = clean(title+' '+employment+' '+description)
    negative = re.search(r'\bonly\s+(?:considering\s+)?(?:direct\s+)?w[ -]?2\b|\bw[ -]?2\s+(?:candidates?\s+)?only\b|\b(?:no|not|without)\s+(?:\w+\s+){0,3}'+C2C+r'\b|\b'+C2C+r'\s+(?:is\s+)?(?:not|unavailable)|\bw[ -]?2\s*(?:only|required)\b|\bonly\s+w[ -]?2\b|\bno\s+(?:third[ -]party|subcontract)',s,re.I)
    positive = re.search(r'\b'+C2C+r'\b',s,re.I)
    if negative: c2c='Not eligible / W2-only'
    elif positive: c2c='C2C mentioned — verify'
    else: c2c='C2C unspecified'
    contract = bool(re.search(r'\b(contract(?:or|ual)?|contract-to-hire|c2h|temporary|freelance|corp-to-corp|c2c)\b',title+' '+employment,re.I))
    if not contract:
        contract = bool(re.search(r'\b(?:\d+[ -]?(?:month|week|year)s?\s+contract|contract\s*:\s*\d+|contract\s+(?:role|position|opportunity|duration)|employment\s+type\s*:?\s*contract)\b',description,re.I))
    fulltime = bool(re.search(r'full[ -]?time|permanent',employment,re.I))
    kind = 'Contract' if contract else ('Permanent / full-time' if fulltime else 'Employment unverified')
    rate = re.search(r'(?:USD\s*|\$)\s*\d{2,3}(?:\.\d{1,2})?(?:\s*[-–to]+\s*\$?\s*\d{2,3}(?:\.\d{1,2})?)?\s*(?:/\s*(?:hr|hour)|per\s+hour|hourly)',s,re.I)
    skills = [x for x in ['Snowflake','Cortex','Fabric','Azure','AWS','GCP','Databricks','Palantir','Foundry','ETL','Python','SQL','dbt','Kafka'] if re.search(r'\b'+x+r'\b',s,re.I)]
    return {'related':bool(ROLE.search(title)), 'contract_type':kind,'c2c':c2c,'eligibility_evidence':negative.group(0) if negative else (positive.group(0) if positive else 'No explicit C2C statement found'), 'hourly_rate':rate.group(0) if rate else '', 'skills':skills}

def normalize(raw):
    j=dict(raw)
    for key in ['title','company','location','description','employment']:
        j[key]=clean(j.get(key,''))
    j['url']=canonical_url(j.get('url',''))
    if not j['url'] or not j['title']: raise ValueError('Job requires a title and HTTPS application URL')
    j['posted_at']=timestamp(j.get('posted_at'))
    j['publisher_time']=timestamp(j.get('publisher_time'))
    j['first_seen']=j.get('first_seen') or now()
    j['last_seen']=now()
    j['region']=region(j['location'])
    j.update(classify(j['title'],j['description'],j['employment']))
    j['id']=hashlib.sha256(j['url'].encode()).hexdigest()[:24]
    j['sources']=[{'source':j.get('source','Manual'),'url':j['url']}]
    return j

def deduplicate(jobs):
    # Exact URL, or same employer + requisition ID. Avoid merging distinct similar vacancies.
    result={}; aliases={}
    for job in jobs:
        j=dict(job)
        keys=['url:'+j['url']]
        if j.get('requisition_id'):
            keys.append('req:'+j['company'].casefold()+':'+str(j['requisition_id']).casefold())
        identity=next((aliases[k] for k in keys if k in aliases),j['id'])
        if identity in result:
            old=result[identity]
            sources={x['url']:x for x in old['sources']+j['sources']}
            first=min(old['first_seen'],j['first_seen'])
            # Keep the trustworthy earliest original posting time when syndicated copies differ.
            times=[x for x in [old.get('posted_at'),j.get('posted_at')] if x]
            j['posted_at']=min(times) if times else None
            j['sources']=list(sources.values()); j['first_seen']=first; j['id']=identity
        result[identity]=j
        for key in keys: aliases[key]=identity
    return list(result.values())

def select(jobs, hours=0, include_unknown=True, c2c_only=False, include_unverified_region=False, reference=None):
    ref=reference or datetime.now(UTC)
    out=[]
    for j in jobs:
        if not j['related'] or j['contract_type']!='Contract' or j['c2c']=='Not eligible / W2-only': continue
        if c2c_only and j['c2c']!='C2C mentioned — verify': continue
        if j['region'] not in ['Central / Eastern USA','US remote'] and not (include_unverified_region and 'remote' in j['region'].lower()): continue
        d=datetime.fromisoformat(j['posted_at']) if j.get('posted_at') else None
        if d and d > ref: d=None  # Future publisher timestamps never prove freshness.
        if hours and (not d or d < ref-timedelta(hours=hours)): continue
        if not hours and not d and not include_unknown: continue
        out.append(j)
    return sorted(out,key=lambda j: j['posted_at'] if j.get('posted_at') and datetime.fromisoformat(j['posted_at'])<=ref else '',reverse=True)
