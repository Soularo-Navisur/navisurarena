import re, os

SRC = 'core.py'
OUT_DIR = 'migrations/versions'
os.makedirs(OUT_DIR, exist_ok=True)

with open(SRC, 'r') as f:
    src = f.read()

migs = []

# 1) Triple-quoted SQL blocks (CREATE TABLE + multi-line inserts)
for block in re.findall(r"[c]\.execute\('''(.*?)'''\)", src, re.DOTALL):
    sql = block.strip()
    if sql:
        migs.append(sql.rstrip(';') + ';')

# 2) Single-line ALTER / CREATE INDEX / INSERT / UPDATE wrapped in try/except
for line in src.splitlines():
    line = line.strip()
    # catch try: conn/c.execute("...") or c.execute(f"...")
    m = re.search(r'(?:conn|c)\.execute\([rf]*"""(.*?)"""\)', line)
    if not m:
        m = re.search(r'(?:conn|c)\.execute\([rf]*\'\'\'(.*?)\'\'\'\)', line)
    if not m:
        m = re.search(r'(?:conn|c)\.execute\([rf]*"([^"]+)"\)', line)
    if not m:
        m = re.search(r"(?:conn|c)\.execute\([rf]*'([^']+)'\)", line)
    if m:
        sql = m.group(1)
        # filter f-strings that aren't pure SQL (contain {var})
        if re.search(r'\{[^}]+\}', sql):
            # check if it's a simple f-string we can static-ify for migration
            continue
        upper = sql.upper().strip()
        if any(upper.startswith(x) for x in ['ALTER','CREATE INDEX','INSERT','UPDATE','DELETE','PRAGMA']):
            migs.append(sql.rstrip(';') + ';')

# Deduplicate preserving order
seen = set()
unique = []
for sql in migs:
    # normalize whitespace
    key = ' '.join(sql.split())
    if key not in seen:
        seen.add(key)
        unique.append(sql)

# Split: first file = CREATE TABLE, second = everything else
first, second = [], []
for sql in unique:
    if re.match(r'CREATE\s+TABLE', sql, re.I):
        first.append(sql)
    else:
        second.append(sql)

with open(f'{OUT_DIR}/001_initial_schema.sql', 'w') as f:
    f.write('-- 001_initial_schema.sql\n\n')
    for s in first:
        f.write(s + '\n\n')

with open(f'{OUT_DIR}/002_v9_3_to_v9_9.sql', 'w') as f:
    f.write('-- 002_v9_3_to_v9_9.sql\n\n')
    for s in second:
        f.write(s + '\n\n')

print(f'Wrote {len(first)} creates, {len(second)} alters/inserts/indices')
