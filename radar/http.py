import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def get_json(url):
    for attempt in range(3):
        try:
            req=Request(url,headers={'User-Agent':'ContractRadar/1.0 (personal public-job-board reader)','Accept':'application/json'})
            with urlopen(req,timeout=25) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt==2: raise
            delay=min(int(exc.headers.get('Retry-After','2')) if exc.headers.get('Retry-After','2').isdigit() else 2,15)
            time.sleep(delay*(attempt+1))
