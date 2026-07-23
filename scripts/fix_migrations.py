import re
with open('core.py') as f: lines = f.readlines()
alters=[]
for line in lines:
    s=line.strip()
    for pat in ['ALTER TABLE','CREATE INDEX','INSERT INTO','UPDATE ','DELETE FROM']:
        if pat in s.upper():
            # strip python wrapper
            sql = re.sub(r'.*execute\([rf]*["\']','',s)
            sql = re.sub(r'["\'].*','',sql)
            sql = sql.replace('\\n',' ').strip()
            if '{' in sql or not sql.upper().startswith(pat.strip()):
                continue
            sql = sql.rstrip(';')+';'
            if sql not in alters: alters.append(sql)
            break
with open('migrations/versions/002_v9_3_to_v9_9.sql','a') as f:
    for s in alters:
        f.write(s+'\n\n')
print('Added',len(alters))
