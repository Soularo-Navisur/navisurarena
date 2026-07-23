import re, ast
with open('core.py') as f: src = f.read()

alters=[]
# find all execute(...) calls
for m in re.finditer(r'c\.execute\((.*?)\)(?:\s*\n)?', src, re.DOTALL):
    arg = m.group(1).strip()
    if arg.startswith('f'):
        arg = arg[1:]
    if arg.startswith('"""') or arg.startswith("'''"):
        continue
    if arg.startswith('"') or arg.startswith("'"):
        # try to extract first string literal
        try:
            q = arg[0]
            end = arg.find(q, 1)
            if end == -1: continue
            sql = ast.literal_eval(arg[:end+1])
        except Exception:
            continue
        up = sql.upper().strip()
        if any(up.startswith(x) for x in ['ALTER TABLE','CREATE INDEX','INSERT INTO','UPDATE ','DELETE FROM','PRAGMA ']):
            sql = sql.rstrip(';')+';'
            key = ' '.join(sql.split())
            if key not in [ ' '.join(a.split()) for a in alters ]:
                alters.append(sql)

with open('migrations/versions/002_v9_3_to_v9_9.sql','a') as f:
    for s in alters:
        f.write(s+'\n\n')
print('Added',len(alters),'new alters')
