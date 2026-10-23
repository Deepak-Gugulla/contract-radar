import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st
from radar.core import normalize, select
from radar.store import get_store, merge_jobs, set_status
from radar.collectors import collect
from radar.assistant import evidence

st.set_page_config(page_title='Contract Radar',page_icon='📡',layout='wide')
st.markdown('''<style>.block-container{max-width:1180px;padding-top:2rem}h1{letter-spacing:-1.6px}.stButton button{border-radius:10px}@media(max-width:640px){.block-container{padding:1rem}.stButton button{min-height:44px}}</style>''',unsafe_allow_html=True)
config=dict(os.environ)
try: config.update(dict(st.secrets))
except FileNotFoundError: pass
password_hash=config.get('APP_PASSWORD_SHA256')
if not password_hash and config.get('REQUIRE_DURABLE','false').lower()=='true':
    st.error('Set APP_PASSWORD_SHA256 in deployment secrets before using this private dashboard.'); st.stop()
if password_hash and not st.session_state.get('authenticated'):
    st.title('📡 Contract Radar'); st.caption('Your private Data Engineering job desk')
    with st.form('login'):
        password=st.text_input('Dashboard password',type='password')
        submit=st.form_submit_button('Sign in')
    if submit:
        if hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),password_hash):
            st.session_state.authenticated=True; st.rerun()
        st.error('Incorrect password.')
    st.stop()

@st.cache_resource
def connect(repo,token,branch,require,local):
    return get_store({'DATA_REPO':repo,'DATA_TOKEN':token,'DATA_BRANCH':branch,'REQUIRE_DURABLE':require,'LOCAL_DB':local})
try:
    store=connect(config.get('DATA_REPO',''),config.get('DATA_TOKEN',''),config.get('DATA_BRANCH','main'),config.get('REQUIRE_DURABLE','false'),config.get('LOCAL_DB','data/local.sqlite'))
    catalog=store.read('catalog',{'jobs':[],'health':[]}); statuses=store.read('status',{})
except Exception as exc:
    st.error(f'Storage is unavailable ({type(exc).__name__}). Check repository access and secrets. No changes have been discarded into temporary storage.'); st.stop()

st.title('📡 Contract Radar')
st.write('**Data Engineering contracts. Freshness first. Your next move, in one place.**')
st.caption('Central & Eastern USA · US remote · C2C signals · No paid APIs')
if not store.durable: st.warning('Local development mode: SQLite persists on this computer only. Configure private GitHub storage before cloud deployment.')
with st.sidebar:
    st.subheader('Your search')
    window=st.selectbox('Original posting age',['Any time','1 hour','3 hours','6 hours','12 hours','24 hours'])
    hours=0 if window=='Any time' else int(window.split()[0])
    unknown=st.checkbox('Include unknown original posting dates',value=True,disabled=bool(hours))
    c2c=st.checkbox('Only jobs mentioning C2C',value=False)
    region_unknown=st.checkbox('Include remote with unverified US eligibility',value=False)
    query=st.text_input('Search title, company or skills',placeholder='Snowflake, Azure, Fabric…')
    view=st.radio('Workspace',['Discover','Saved','Applied','Skipped','Viewed'])
    st.divider(); st.caption('Scheduled collection: every 2 hours once GitHub Actions is enabled. Delays are possible.')
    refreshed=catalog.get('refreshed_at'); st.caption('Last collection: '+(refreshed or 'Not collected yet'))
    can_refresh=not refreshed or datetime.now(timezone.utc)-datetime.fromisoformat(refreshed)>timedelta(minutes=5)
    if st.button('↻ Collect now',width='stretch',disabled=not can_refresh):
        try:
            with st.spinner('Reading configured public boards…'):
                new_jobs,health=collect(json.loads(Path('sources.json').read_text())['sources'])
                merge_jobs(store,new_jobs,health)
            st.rerun()
        except Exception as exc: st.error(f'Collection could not be saved ({type(exc).__name__}). Try again.')
    if st.button('Reload saved data',width='stretch'): st.rerun()
    if password_hash and st.button('Sign out'): st.session_state.clear(); st.rerun()
all_jobs=catalog.get('jobs',[])
if view=='Discover':
    jobs=select(all_jobs,hours,unknown,c2c,region_unknown)
    jobs=[j for j in jobs if statuses.get(j['id'],{}).get('status') not in ('skip','applied')]
else:
    expected={'Saved':'save','Applied':'applied','Skipped':'skip'}
    jobs=[r['job'] for r in statuses.values() if r.get('job') and (bool(r.get('viewed_at')) if view=='Viewed' else r.get('status')==expected[view])]
    jobs.sort(key=lambda j:j.get('posted_at') or '',reverse=True)
    st.caption('History retains snapshots. Discovery eligibility and age filters do not hide saved records.')
if query: jobs=[j for j in jobs if query.casefold() in (' '.join([j['title'],j['company'],j['description']])).casefold()]
a,b,c=st.columns(3)
a.metric('Matching jobs',len(jobs)); b.metric('C2C mentioned',sum(j['c2c']=='C2C mentioned — verify' for j in jobs)); c.metric('Original date unknown',sum(not j.get('posted_at') for j in jobs))
st.caption('Newest original posting first • Unknown originals last • C2C mention is a signal, not recruiter confirmation')
def perform(j,action):
    try: set_status(store,j,action); st.rerun()
    except Exception as exc: st.error(f'Could not save {action} ({type(exc).__name__}). Please retry.')
def format_time(value): return datetime.fromisoformat(value).astimezone(ZoneInfo('America/New_York')).strftime('%b %d, %Y · %I:%M %p ET')
if not jobs: st.info('No matching contracts. Collect sources, choose Any time, or add staffing/company boards in sources.json. Full-time and W2-only roles stay excluded.')
page=st.number_input('Page',min_value=1,max_value=max(1,(len(jobs)+19)//20),value=1,step=1)
for j in jobs[(page-1)*20:page*20]:
    with st.container(border=True):
        st.subheader(j['title']); st.write(f"**{j['company']}** · {j['location']}")
        st.caption(' · '.join([j['contract_type'],j['c2c'],j.get('hourly_rate') or 'Hourly rate not listed']))
        original=j.get('posted_at')
        st.write('Posted '+format_time(original) if original and datetime.fromisoformat(original)<=datetime.now(timezone.utc) else 'Original posting time **unknown / unverified**')
        if j.get('publisher_time'): st.caption('Last publication (may be a repost): '+format_time(j['publisher_time']))
        st.caption(j.get('time_basis','User-provided posting time')+' · First discovered '+format_time(j['first_seen']))
        st.caption('Skills: '+(', '.join(j['skills']) or 'See description')+' · '+j['region'])
        cols=st.columns(5)
        for col,label,action in zip(cols[:4],['Save','Skip','Applied','Viewed'],['save','skip','applied','viewed']):
            if col.button(label,key=action+j['id'],width='stretch'): perform(j,action)
        cols[4].link_button('Apply ↗',j['url'],width='stretch')
        st.caption('Apply opens the original listing. Mark Viewed or Applied explicitly; opening a link does not submit an application.')
        record=statuses.get(j['id'],{})
        if record.get('status') or record.get('viewed_at'):
            st.caption('Your activity: '+record.get('status','')+(' · Viewed' if record.get('viewed_at') else ''))
            if st.button('Reset status',key='r'+j['id']): perform(j,'reset')
        with st.expander('Description & local AI evidence'):
            st.caption('Free TF-IDF extraction selects source sentences. It does not verify C2C, infer dates, or reorder jobs.')
            try:
                for sentence in evidence(j['description']): st.info(sentence)
            except Exception: st.caption('Local analysis unavailable; full source text is below.')
            st.write('Eligibility evidence: '+j['eligibility_evidence']); st.text(j['description'])
            for source in j['sources']: st.link_button(source['source'],source['url'])
with st.expander('Source health & coverage'):
    st.dataframe(catalog.get('health',[]),width='stretch')
    st.caption('Configured boards only—not the whole internet. Previous listings may have closed; verify the application page.')
with st.expander('Import authorized jobs / LinkedIn alert details'):
    st.write('Upload a JSON array of job objects you are authorized to use. Copy LinkedIn alert details into the supplied template. Alert arrival time is never the posting time. No inbox access or LinkedIn scraping is performed.')
    upload=st.file_uploader('Job JSON',type=['json'])
    if upload and st.button('Import jobs'):
        try:
            raw=json.load(upload)
            if not isinstance(raw,list) or len(raw)>200: raise ValueError('Use an array of up to 200 jobs')
            merge_jobs(store,[normalize({**x,'source':x.get('source','Authorized manual import')}) for x in raw])
            st.success(f'Imported {len(raw)} jobs. Reload saved data to view them.')
        except Exception as exc: st.error(f'Import failed: {type(exc).__name__}. Check the template and HTTPS URLs.')
with st.expander('Export your private data'):
    st.download_button('Download catalog and activity',json.dumps({'catalog':catalog,'status':statuses},indent=2),'contract-radar-backup.json','application/json')
