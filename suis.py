"""Public SUIS catalog adapter. No credentials; server-side only.

SUIS pages are third-party HTML: always retain sources and mark unparsed rules
as requiring manual verification. In-memory TTL cache avoids excessive traffic.
"""
from __future__ import annotations
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

BASE = 'https://suis.sabanciuniv.edu'
LIST = BASE + '/prod/SU_DEGREE.p_list_degree'
TERM = BASE + '/prod/SU_DEGREE.p_select_term'
DETAIL = BASE + '/prod/SU_DEGREE.p_degree_detail'
HEADERS = {'User-Agent': 'SUGradPlanner/0.1 (student prototype; catalog cache)'}
CACHE = {}
TTL = 6 * 3600
CODE = re.compile(r'^([A-Z]{2,6})\s*([0-9]{3}[A-Z]?)$')
CAT_NAMES = ('Üniversite Dersleri', 'Zorunlu Dersler', 'Çekirdek Seçmeli Dersler', 'Alan Seçmeli Dersler', 'Serbest Seçmeli Dersler', 'Fakülte Dersleri', 'Mühendislik', 'Temel Bilim')

class UpstreamError(Exception):
    pass

def html(url, params=None):
    if not url.startswith(BASE + '/prod/'):
        raise ValueError('Only the SUIS public catalog is allowed')
    key = (url, tuple(sorted((params or {}).items())))
    old = CACHE.get(key)
    if old and time.time() - old[0] < TTL:
        return old[1]
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        CACHE[key] = (time.time(), soup)
        return soup
    except requests.RequestException as exc:
        raise UpstreamError('SUIS şu anda erişilebilir değil. Daha sonra tekrar deneyin.') from exc

def valid_program(value):
    return bool(re.fullmatch('[A-Z0-9]{2,12}', value))

def valid_term(value):
    return bool(re.fullmatch(r'20\d{4}|19\d{4}', value))

def programs():
    soup = html(LIST, {'P_LEVEL':'UG','P_LANG':'TR','P_PRG_TYPE':''})
    out = {}
    for a in soup.select('a[href]'):
        href = urljoin(BASE, a['href'])
        p = parse_qs(urlparse(href).query).get('P_PROGRAM', [''])[0]
        if valid_program(p) and 'p_select_term' in href:
            out[p] = {'code':p, 'name':a.get_text(' ', strip=True)}
    if not out:
        raise UpstreamError('SUIS bölüm listesi çözümlenemedi; sayfa yapısı değişmiş olabilir.')
    return list(out.values())

def term_label(term):
    """Presentation only: YYYY is the academic year's starting year.

    Official SUIS confirms 01=Fall, 02=Spring and 03=Summer. Other suffixes
    deliberately stay unclassified; never infer their season from a number.
    """
    if not valid_term(term): raise ValueError('Geçersiz dönem')
    season = {'01': 'Güz', '02': 'Bahar', '03': 'Yaz'}.get(term[-2:])
    if season is None:
        return f'SUIS {term} · Dönem adı doğrulanmadı'
    year = int(term[:4])
    return f'{year}-{year + 1} {season}'


def term_sort_key(term):
    # Newest academic year first, then Fall / Spring / Summer / unknown.
    return (-int(term[:4]), {'01': 0, '02': 1, '03': 2}.get(term[-2:], 3), term)


def terms(program):
    if not valid_program(program): raise ValueError('Geçersiz bölüm')
    soup = html(TERM, {'P_LANG':'TR','P_LEVEL':'UG','P_PROGRAM':program})
    found = set()
    for a in soup.select('a[href]'):
        h = urljoin(BASE,a['href'])
        term = parse_qs(urlparse(h).query).get('P_TERM',[''])[0]
        if valid_term(term): found.add(term)
    # Some SUIS pages expose terms via <option> values.
    for o in soup.select('option[value]'):
        v = o['value'].strip()
        if valid_term(v): found.add(v)
    if not found: raise UpstreamError('Bu bölümün giriş dönemleri okunamadı.')
    return [{'code':t,'label':term_label(t)} for t in sorted(found,key=term_sort_key)]

def norm(s):
    return ' '.join(s.split()).strip()


def course_credit(code):
    match = CODE.fullmatch(code)
    if not match: raise ValueError('Geçersiz ders kodu')
    params = {'levl_code': 'UG', 'subj_code': match[1], 'crse_numb': match[2], 'lang': 'tur'}
    endpoint = BASE + '/prod/sabanci_www.p_get_courses'
    source = requests.Request('GET', endpoint, params=params).prepare().url
    soup = html(endpoint, params)
    text = norm(soup.get_text(' ', strip=True))
    # This public course description has no term parameter: these are current
    # catalog values, not a reconstruction of credits in the student's admit year.
    credits = re.search(r'\(\s*ENGINEERING\s*:\s*(\d+(?:[.,]\d+)?)\s*/\s*BASIC\s*:\s*(\d+(?:[.,]\d+)?)\s*\)', text, re.I)
    prerequisites = None
    for heading in soup.find_all(['b', 'strong', 'th']):
        label = norm(heading.get_text(' ', strip=True))
        plain = ''.join(c for c in unicodedata.normalize('NFD', label.lower()) if not unicodedata.combining(c)).replace('ı', 'i')
        if not re.fullmatch(r'(?:on\s*kosul(?:lar[ıi]?)?|prerequisites?)\s*:?', plain): continue
        cell = heading if heading.name == 'th' else heading.parent
        content = norm(cell.get_text(' ', strip=True))
        value = content[len(label):].lstrip(' :') if content.startswith(label) else ''
        if not value and cell.name in ('td', 'th'):
            sibling = cell.find_next_sibling(['td', 'th'])
            if sibling: value = norm(sibling.get_text(' ', strip=True))
        if value and value.casefold() not in ('yok', 'none', 'n/a', '-', '—'):
            # Preserve alternative courses, required grades and AND/OR wording.
            prerequisites = value
        break
    return {'code': f'{match[1]} {match[2]}',
            'engineering': float(credits[1].replace(',', '.')) if credits else None,
            'basic': float(credits[2].replace(',', '.')) if credits else None,
            'prerequisites': prerequisites,
            'source_url': source, 'credit_basis': 'current_catalog'}

def parse_courses(table, category):
    courses=[]
    if not table: return courses
    for tr in ([table] if table.name == 'tr' else table.select('tr')):
        cells=tr.find_all(['td','th'],recursive=False)
        values=[norm(c.get_text(' ',strip=True)) for c in cells]
        if len(values)<4: continue
        # Search cell beginning for a single course code; do not use arbitrary
        # numeric text or the linked course title as course code.
        idx=None; match=None
        for i,x in enumerate(values[:3]):
            m=CODE.fullmatch(x)
            if m: idx=i;match=m;break
        if idx is None:continue
        after=values[idx+1:]
        numeric=[(i,float(x.replace(',','.'))) for i,x in enumerate(after) if re.fullmatch(r'\d+(?:[.,]\d+)?',x)]
        if len(numeric)<2: continue
        ec=numeric[0][1];su=numeric[1][1]
        title=after[0] if after and not re.fullmatch(r'\d+',after[0]) else ''
        code=f'{match.group(1)} {match.group(2)}'
        courses.append({'code':code,'name':title,'ects':ec,'su':su,'category':category})
    return courses

def required_credits(soup):
    # Read the explicit total; category thresholds can overlap and must not
    # be summed to invent a graduation-credit target.
    totals=set()
    for row in soup.select('tr'):
        values=[norm(cell.get_text(' ',strip=True)) for cell in row.find_all(['td','th'],recursive=False)]
        if len(values)!=4 or values[0].casefold() not in ('toplam','total'):continue
        if not all(re.fullmatch(r'-|\d+(?:[.,]\d+)?',v) for v in values[1:]):continue
        totals.add(tuple(None if v=='-' else float(v.replace(',','.')) for v in values[1:3]))
    if len(totals)!=1:return {'ects':None,'su':None}
    ects,su=totals.pop()
    return {'ects':ects,'su':su}


def detail(program,term):
    if not valid_program(program) or not valid_term(term):raise ValueError('Geçersiz bölüm veya dönem')
    params = {'P_LANG':'TR','P_LEVEL':'UG','P_PROGRAM':program,'P_SUBMIT':'Select','P_TERM':term}
    url = requests.Request('GET',DETAIL,params=params).prepare().url
    soup = html(DETAIL,params)
    title = next((norm(h.get_text(' ',strip=True)) for h in soup.find_all(['h1','h2']) if 'LİSANS PROGRAMI' in h.get_text(' ',strip=True)), program)
    categories=[]; course_map={}; pool_links={}; warnings=[]

    def merge(course, source):
        item = course_map.setdefault(course['code'], {
            'code':course['code'], 'name':course['name'], 'ects':course['ects'],
            'su':course['su'], 'categories':[], 'source_urls':[]})
        if course['category'] not in item['categories']: item['categories'].append(course['category'])
        if source not in item['source_urls']: item['source_urls'].append(source)

    # Follow category headings in document order; don't parse enclosing tables
    # under a previous heading (which can misclassify an entire later section).
    current = None
    for element in soup.find_all(['b','strong','tr']):
        label = norm(element.get_text(' ',strip=True))
        if element.name in ('b','strong') and label in CAT_NAMES: current = label
        elif element.name == 'tr' and current:
            for course in parse_courses(element, current): merge(course, url)

    for tr in soup.select('tr'):
        vals=[norm(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
        if len(vals) != 4 or vals[0] not in CAT_NAMES: continue
        metrics=vals[1:]
        if all(re.fullmatch(r'-|\d+(?:[.,]\d+)?',v) for v in metrics):
            def number(v):return None if v=='-' else float(v.replace(',','.'))
            categories.append({'name':vals[0],'min_ects':number(metrics[0]),'min_su':number(metrics[1]),'min_count':number(metrics[2])})

    # Resolve relative links against /prod/, preserve each exact program/term
    # and collect ALL faculty pools instead of overwriting one category link.
    pools = []
    for anchor in soup.select('a[href]'):
        href = urljoin(DETAIL, anchor['href'].strip())
        parsed = urlparse(href)
        if parsed.scheme != 'https' or parsed.netloc != urlparse(BASE).netloc or parsed.path != '/prod/SU_DEGREE.p_list_courses': continue
        query = parse_qs(parsed.query)
        if query.get('P_TERM') != [term] or query.get('P_PROGRAM') != [program]: continue
        area = query.get('P_AREA', [''])[0]
        category = {program+'_CEL':'Çekirdek Seçmeli Dersler',program+'_AEL':'Alan Seçmeli Dersler',program+'_FEL':'Serbest Seçmeli Dersler'}.get(area)
        if area.startswith('FC_'): category = 'Fakülte Dersleri'
        if category is None:
            # Match named section anchors for other degree-specific pool names.
            section = soup.find('a', attrs={'name': area})
            heading = section.parent.find(['b','strong']) if section and section.parent else None
            if heading and norm(heading.get_text()) in CAT_NAMES: category = norm(heading.get_text())
        if category and href not in [h for _,h in pools]:
            pools.append((category,href))
            pool_links.setdefault(category,[]).append(href)

    def read_pool(pool):
        category, href = pool
        try:
            courses = parse_courses(html(href), category)
            if not courses: return category, href, [], 'Ders havuzu okunamadı: '+category
            return category, href, courses, None
        except UpstreamError:
            return category, href, [], 'Ders havuzuna ulaşılamadı: '+category
    with ThreadPoolExecutor(max_workers=4) as executor:
        for category, href, courses, warning in executor.map(read_pool,pools):
            if warning: warnings.append(warning)
            for course in courses: merge(course,href)

    notes=[]
    for element in soup.find_all('p'):
        sentence=norm(element.get_text(' ',strip=True))
        if any(word in sentence.lower() for word in ('veya','fazladan','en az','sayılır','sayılmaz','zorunlu')):
            if 15<len(sentence)<900 and sentence not in notes:notes.append(sentence)
    return {'program':program,'term':term,'title':title,'source_url':url,'required':required_credits(soup),'requirements':categories,
            'courses':sorted(course_map.values(),key=lambda x:x['code']),'notes':notes[:20],
            'pool_links':pool_links,'catalog_warnings':warnings,'needs_official_verification':True}
