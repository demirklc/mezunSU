"""Build public, source-attributed SUIS snapshots for GitHub Pages."""
import sys,json,time,argparse,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import suis
# Four program jobs, two pool requests each: at most eight concurrent SUIS requests.
suis.ThreadPoolExecutor=lambda max_workers: ThreadPoolExecutor(max_workers=2)
ROOT=Path('site/data')
ALIASES={'CS 210':'DSA 210','PROJ 102':'PROJ 201'}
def read(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return default
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def normalize(degree):
    courses={}
    for c in degree['courses']:
        code=ALIASES.get(c['code'],c['code'])
        if code in courses:courses[code]['categories']=sorted(set(courses[code]['categories']+c['categories']))
        else:courses[code]={**c,'code':code}
    return {**degree,'courses':list(courses.values())}
def discover():
    programs=suis.programs()
    write(ROOT/'programs.json',programs)
    write(ROOT/'manifest.json',{'updated_at':time.time(),'source':'https://suis.sabanciuniv.edu'})
    print(json.dumps([p['code'] for p in programs]))
def program(code):
    terms=suis.terms(code)
    available=[];failed=[]
    for t in terms:
        path=ROOT/'curriculum'/code/(t['code']+'.json')
        old=read(path,None)
        if old and time.time()-old.get('updated_at',0)<7*86400:
            available.append(t);continue
        try:
            d=normalize(suis.detail(code,t['code']))
            if not d['requirements'] or not d['courses'] or d.get('catalog_warnings'):raise suis.UpstreamError('Incomplete curriculum')
            d['updated_at']=time.time();write(path,d);available.append(t)
        except suis.UpstreamError:
            failed.append(t['code'])
            if old:available.append(t)
        print(code,t['code'],'saved' if t in available else 'unavailable',flush=True)
    if not available:raise RuntimeError('No verified curriculum for '+code)
    # Include all official choices; unavailable data shows an explicit error.
    write(ROOT/'terms'/(code+'.json'),terms)
    write(ROOT/'status'/(code+'.json'),{'updated_at':time.time(),'available':len(available),'total':len(terms),'failed':failed})
def credits():
    old=read(ROOT/'credits.json',{})
    codes=sorted({c['code'] for path in (ROOT/'curriculum').glob('*/*.json') for c in read(path,{}) .get('courses',[])})
    lock=threading.Lock();last=[0.0]
    def fetch(code):
        cached=old.get(code)
        if cached and time.time()-cached.get('updated_at',0)<7*86400:return code,cached
        with lock:
            time.sleep(max(0,.35-(time.monotonic()-last[0])));last[0]=time.monotonic()
        try:
            value=suis.course_credit(code)
            return code,{**value,'updated_at':time.time()}
        except suis.UpstreamError:return code,cached or {'code':code,'engineering':None,'basic':None,'prerequisites':None,'updated_at':0,'_unavailable':True}
    with ThreadPoolExecutor(max_workers=2) as executor:
        for i,(code,value) in enumerate(executor.map(fetch,codes)):
            old[code]=value
            if i%50==0:print('Credits',i+1,'/',len(codes),flush=True)
    write(ROOT/'credits.json',old)
    write(ROOT/'manifest.json',{'updated_at':time.time(),'courses':len(codes),'source':'https://suis.sabanciuniv.edu'})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['discover','program','credits']);parser.add_argument('--program');args=parser.parse_args()
    if args.mode=='discover':discover()
    elif args.mode=='program':program(args.program)
    else:credits()
