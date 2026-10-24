"""Read-only review of changed publication candidates and local links."""
from pathlib import Path
import json,re,subprocess
import nbformat

repo=Path(__file__).resolve().parents[3]
paths=sorted(set(subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard'],cwd=repo,text=True).splitlines()))
paths=sorted(set(paths+subprocess.check_output(['git','diff','--cached','--name-only'],cwd=repo,text=True).splitlines()))
if not paths:raise SystemExit('No publication candidates')
for name in paths:
    p=repo/name
    assert p.suffix in ('.py','.cjs','.md','.ipynb'),name
    assert '/data/' not in name and p.stat().st_size<1024**2,name
    content=p.read_text(encoding='utf-8-sig')
    pattern=r'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY'
    assert not re.search(pattern,content) and ('X-Amz-'+'Signature=') not in content,name
    if p.suffix=='.ipynb':
        n=nbformat.read(p,as_version=4);nbformat.validate(n)
        assert all(not c.get('outputs') and c.get('execution_count') is None and not c.get('attachments') for c in n.cells),name
        assert set(n.metadata)<= {'kernelspec','language_info'},name
    if p.suffix=='.md':
        for u in re.findall(r'\]\(([^)]+)\)',content):
            if not re.match(r'[a-z]+://|#',u):assert (p.parent/u.split('#')[0]).exists(),(name,u)
    print(name,p.stat().st_size)
print('Candidate extensions, sizes, secret patterns, local document links and Notebook outputs: PASS')
