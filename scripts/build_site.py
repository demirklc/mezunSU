"""Assemble the static site from source assets and prepared public data."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def build():
    site=ROOT/'site'
    if not (site/'data/programs.json').is_file() or not (site/'data/credits.json').is_file():
        raise SystemExit('Public snapshots are not ready. Fetch the snapshots branch first.')
    (site/'static').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'static/index.html',site/'index.html')
    for pattern in ('*.js','*.png'):
        for path in (ROOT/'static').glob(pattern):shutil.copy2(path,site/'static'/path.name)
    shutil.copy2(ROOT/'static/rehber.html',site/'rehber.html')
    (site/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://demirklc.github.io/mezunSU/</loc></url><url><loc>https://demirklc.github.io/mezunSU/rehber.html</loc></url></urlset>',encoding='utf-8')
    (site/'.nojekyll').touch()
if __name__=='__main__':build()
