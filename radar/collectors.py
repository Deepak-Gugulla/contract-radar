"""Documented public ATS APIs only. Never use login cookies or scrape LinkedIn."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from .http import get_json
from .core import normalize, now, ROLE, clean


def collect_board(board):
    kind=board['type']; slug=quote(board['board'],safe=''); company=board['company']
    output=[]
    if kind=='greenhouse':
        data=get_json(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true')['jobs']
        for j in data:
            if not ROLE.search(j['title']): continue
            metadata=' '.join(str(m.get('value','')) for m in j.get('metadata',[]))
            output.append(normalize(dict(title=j['title'],company=company,location=j.get('location',{}).get('name',''),description=j.get('content',''),employment=metadata,url=j['absolute_url'],posted_at=j.get('first_published'),time_basis='Greenhouse first_published' if j.get('first_published') else 'Original posting time unavailable',requisition_id=j.get('requisition_id'),source='Greenhouse')))
    elif kind=='lever':
        data=[]; skip=0
        while True:
            page=get_json(f'https://api.lever.co/v0/postings/{slug}?mode=json&limit=100&skip={skip}')
            data.extend(page)
            if len(page)<100: break
            skip+=100
            if skip>=10000: raise ValueError('Board exceeds 10,000 postings; configure a narrower source')
        for j in data:
            if not ROLE.search(j['text']): continue
            cat=j.get('categories',{})
            desc=' '.join([j.get('descriptionPlain',''),j.get('additionalPlain','')]+[clean(x.get('content','')) for x in j.get('lists',[])])
            salary=j.get('salaryRange') or {}
            if salary.get('interval') in ['per-hour','hour']:
                desc+=f" ${salary.get('min')}-${salary.get('max')} per hour"
            output.append(normalize(dict(title=j['text'],company=company,location=cat.get('location','')+(' Remote' if j.get('workplaceType')=='remote' else ''),description=desc,employment=cat.get('commitment',''),url=j['hostedUrl'],posted_at=None,time_basis='Lever public API: original posting time unavailable',source='Lever')))
    elif kind=='ashby':
        data=get_json(f'https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true')['jobs']
        for j in data:
            if not j.get('isListed',True) or not ROLE.search(j['title']): continue
            address=(j.get('address') or {}).get('postalAddress',{})
            location='; '.join([j.get('location','')]+[s.get('location','') for s in j.get('secondaryLocations',[])]+[address.get('addressCountry','')])+(' Remote' if j.get('isRemote') else '')
            desc=j.get('descriptionPlain','')+' '+(j.get('compensation') or {}).get('compensationTierSummary','')
            output.append(normalize(dict(title=j['title'],company=company,location=location,description=desc,employment=j.get('employmentType',''),url=j.get('jobUrl') or j['applyUrl'],posted_at=None,publisher_time=j.get('publishedAt'),time_basis='Ashby last publication (may be a repost); original time unknown',source='Ashby')))
    elif kind=='json_feed':
        if not board.get('permission_confirmed'): raise ValueError('Feed permission must be confirmed in sources.json')
        data=get_json(board['url'])
        for row in data['jobs']:
            output.append(normalize({**row,'company':row.get('company',company),'source':board.get('label','Authorized JSON feed')}))
    else: raise ValueError('Unsupported source type: '+kind)
    return output,len(data)


def collect(boards):
    jobs=[]; health=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(collect_board,b):b for b in boards if b.get('enabled',True)}
        for future in as_completed(futures):
            b=futures[future]
            try:
                rows,count=future.result(); jobs.extend(rows)
                health.append({'source':b['type'],'board':b['board'],'ok':True,'total':count,'related':len(rows),'checked_at':now()})
            except Exception as e:
                health.append({'source':b['type'],'board':b['board'],'ok':False,'error':str(e)[:250],'checked_at':now()})
    return jobs,health
