import glob, sys
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
bad=[]
for pat in ['data/*.json','data/*/*.json','*.json']:
    for fp in glob.glob(pat):
        try:
            open(fp,encoding='utf-8').read()
        except UnicodeDecodeError as e:
            bad.append((fp,str(e)[:50]))
if bad:
    print("=== 非 UTF-8 的坏档 ===")
    for fp,e in bad: print(f"  {fp}  ({e})")
else:
    print("所有 JSON 都是 UTF-8, 没有坏档")
