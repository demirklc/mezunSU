from __future__ import annotations
import json,os,sqlite3,threading,time,re,hashlib,base64
from pathlib import Path
from contextlib import contextmanager
from collections import defaultdict,deque
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
import suis
ROOT=Path(__file__).parent
CACHE_DIR=Path(os.environ.get('CACHE_DIR',str(ROOT/'data')))
DB=str(CACHE_DIR/'public-cache.sqlite3')
app=FastAPI(title='mezunSU Public Catalog',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
ALIASES={'CS 210':'DSA 210','PROJ 102':'PROJ 201'}
def canonical(code):return ALIASES.get(code,code)
credit_locks=[threading.Lock() for _ in range(32)]
credit_slots=threading.BoundedSemaphore(2)
credit_rate_lock=threading.Lock()
credit_last_request=0.0
CREDIT_TTL=7*24*3600
CREDIT_PARTIAL_TTL=6*3600

@contextmanager
def credit_connection():
    path=os.environ.get('CREDIT_DB_PATH',str(Path(DB).with_name('course_credit_cache.sqlite3')))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=30)
    c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS credit_cache(code TEXT PRIMARY KEY,data TEXT NOT NULL,fetched_at REAL NOT NULL,retry_after REAL NOT NULL DEFAULT 0)')
    c.commit()
    try:
        with c:yield c
    finally:c.close()

def cached_record(code):
    with credit_connection() as c:row=c.execute('SELECT * FROM credit_cache WHERE code=?',(code,)).fetchone()
    if not row:return None
    return credit_record_data(row)

def credit_record_data(row):
    data=json.loads(row['data'])
    ttl=CREDIT_TTL if data.get('engineering') is not None and data.get('basic') is not None else CREDIT_PARTIAL_TTL
    return {**data,'_cache':{'fresh':bool(row['fetched_at'] and time.time()-row['fetched_at']<ttl),
            'fetched_at':row['fetched_at'],'retry_after':row['retry_after']}}

def cached_credit(code):
    global credit_last_request
    code=canonical(code)
    if not suis.CODE.fullmatch(code):raise ValueError('Geçersiz ders kodu')
    with credit_locks[hash(code)%len(credit_locks)]:
        old=cached_record(code)
        if old and (old['_cache']['fresh'] or old['_cache']['retry_after']>time.time()):return old
        try:
            with credit_slots:
                with credit_rate_lock:
                    pause=.3-(time.monotonic()-credit_last_request)
                    if pause>0:time.sleep(pause)
                    credit_last_request=time.monotonic()
                data=suis.course_credit(code)
            fetched=time.time()
            with credit_connection() as c:
                c.execute('INSERT INTO credit_cache VALUES(?,?,?,0) ON CONFLICT(code) DO UPDATE SET data=excluded.data,fetched_at=excluded.fetched_at,retry_after=0',(code,json.dumps(data,ensure_ascii=False),fetched))
            return {**data,'_cache':{'fresh':True,'fetched_at':fetched,'retry_after':0}}
        except suis.UpstreamError:
            retry=time.time()+60
            with credit_connection() as c:
                c.execute('INSERT INTO credit_cache VALUES(?,?,0,?) ON CONFLICT(code) DO UPDATE SET retry_after=excluded.retry_after',
                          (code,json.dumps({'code':code,'engineering':None,'basic':None,'prerequisites':None}),retry))
            return {**(old or {'code':code,'engineering':None,'basic':None,'prerequisites':None}),
                    '_cache':{'fresh':False,'fetched_at':old['_cache']['fetched_at'] if old else 0,'retry_after':retry},'_unavailable':True}

class CreditCodes(BaseModel):
    codes:list[str]=Field(max_length=1000)

@app.post('/api/course-credit-cache')
def read_credit_cache(query:CreditCodes):
    if any(not suis.CODE.fullmatch(code) for code in query.codes):raise HTTPException(400,'Geçersiz ders kodu')
    credits={}
    with credit_connection() as c:
        for code in dict.fromkeys(canonical(code) for code in query.codes):
            row=c.execute('SELECT * FROM credit_cache WHERE code=?',(code,)).fetchone()
            if row:credits[code]=credit_record_data(row)
    return {'credits':credits}

def normalized_degree(degree):
    courses={}
    for course in degree.get('courses',[]):
        code=canonical(course['code'])
        if code not in courses:courses[code]={**course,'code':code,'categories':list(course.get('categories',[]))}
        else:courses[code]['categories']=sorted(set(courses[code]['categories']+course.get('categories',[])))
    return {**degree,'courses':sorted(courses.values(),key=lambda c:c['code'])}


public_locks=[threading.Lock() for _ in range(16)]
def shared_catalog(key,fetch):
    with public_locks[hash(key)%len(public_locks)]:
        with credit_connection() as c:
            c.execute('CREATE TABLE IF NOT EXISTS catalog_cache(key TEXT PRIMARY KEY,data TEXT NOT NULL,fetched_at REAL NOT NULL)')
            row=c.execute('SELECT * FROM catalog_cache WHERE key=?',(key,)).fetchone()
        if row and time.time()-row['fetched_at']<6*3600:return json.loads(row['data'])
        result=fetch()
        with credit_connection() as c:
            c.execute('INSERT INTO catalog_cache VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,fetched_at=excluded.fetched_at',(key,json.dumps(result,ensure_ascii=False),time.time()))
        return result

@app.get('/')
def home():return FileResponse(ROOT/'static'/'index.html')
@app.get('/health')
async def health():return {'status':'ok'}
@app.get('/api/programs')
def programs():
    try:return shared_catalog('programs',suis.programs)
    except suis.UpstreamError as e:raise HTTPException(503,str(e))
@app.get('/api/terms/{program}')
def terms(program:str):
    if not suis.valid_program(program):raise HTTPException(400,'Geçersiz program')
    try:return shared_catalog('terms:'+program,lambda:suis.terms(program))
    except suis.UpstreamError as e:raise HTTPException(503,str(e))
@app.get('/api/curriculum/{program}/{term}')
def curriculum(program:str,term:str):
    if not suis.valid_program(program) or not suis.valid_term(term):raise HTTPException(400,'Geçersiz program veya dönem')
    try:return normalized_degree(shared_catalog('degree:'+program+':'+term,lambda:suis.detail(program,term)))
    except suis.UpstreamError as e:raise HTTPException(503,str(e))
@app.get('/api/course-credit/{code}')
def course_credit(code:str):
    try:return cached_credit(code)
    except ValueError as e:raise HTTPException(400,str(e))

rate_windows={}
@app.middleware('http')
async def guard_public_api(request:Request,call_next):
    if request.url.path.startswith('/api/'):
        # Do not trust user-supplied forwarding headers to identify callers.
        ip=request.client.host if request.client else 'unknown'
        now=time.monotonic()
        if len(rate_windows)>10000:
            for key in list(rate_windows):
                if not rate_windows[key] or now-rate_windows[key][-1]>60:rate_windows.pop(key,None)
        window=rate_windows.setdefault(ip,deque())
        while window and now-window[0]>60:window.popleft()
        if len(window)>=int(os.environ.get('API_RATE_LIMIT','300')):
            return JSONResponse({'detail':'Çok fazla istek. Kısa süre sonra tekrar deneyin.'},429,headers={'Retry-After':'60'})
        window.append(now)
        if request.method=='POST':
            try:length=int(request.headers.get('content-length','0'))
            except ValueError:return JSONResponse({'detail':'Geçersiz istek'},400)
            if length>65536:return JSONResponse({'detail':'İstek çok büyük'},413)
            if len(await request.body())>65536:return JSONResponse({'detail':'İstek çok büyük'},413)
    response=await call_next(request)
    source=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
    hashes=["'sha256-"+base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()+"'" for script in re.findall(r'<script>(.*?)</script>',source,re.S)]
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' "+' '.join(hashes)+"; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    if request.url.path=='/':response.headers['Cache-Control']='no-cache'
    return response
