# -*- coding: utf-8 -*-
"""Từ fingerprint.log: thời gian giải mã / tổng theo clip của 3 lượt sáng 06/11, so với số đo lúc máy rảnh."""
import collections, datetime as dt, os, re, statistics
L = r'C:\Dev\TimClipPro_DevState\output\fingerprint.log'
KHO = r'E:\Kho_Tool_Quet\Kho_Joe_Games'
JOB = {'6827208101123447975': '08:07', '898880143964983501': '08:19', '5363093045530188980': '09:18'}
re_t = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)')
re_j = re.compile(r'fingerprint\.job\.(\d+)')
re_f = re.compile(r"file=(?:'([^']*)'|\"([^\"]*)\")")
kq = collections.defaultdict(dict)   # job -> file -> dict
for dong in open(L, encoding='utf-8', errors='replace'):
    mj = re_j.search(dong)
    if not mj or mj.group(1) not in JOB:
        continue
    j = JOB[mj.group(1)]
    t = dt.datetime.strptime(re_t.match(dong).group(1), '%Y-%m-%d %H:%M:%S')
    mf = re_f.search(dong)
    if not mf:
        continue
    f = mf.group(1) or mf.group(2)
    d = kq[j].setdefault(f, {})
    if 'event=phase phase=decoding' in dong:
        d.setdefault('dec', t)
    elif 'event=phase phase=fingerprinting' in dong:
        d.setdefault('fp', t)
    elif 'event=clip success' in dong:
        m = re.search(r'elapsed=([0-9.]+)s', dong)
        d['xong'] = t; d['tong'] = float(m.group(1))
    elif 'event=clip failed' in dong:
        d['hong'] = True
kt = {f: os.path.getsize(os.path.join(KHO, f)) / 1e6 for f in os.listdir(KHO) if f.endswith('.opus')}
print('Luc may ranh (bai B): 0.87 s/MB tong; giai ma 1 luong ~0.11 s/MB\n')
for j, ds in kq.items():
    co = [(f, d) for f, d in ds.items() if 'tong' in d and f in kt]
    giai = [((d['fp'] - d['dec']).total_seconds(), kt[f]) for f, d in ds.items() if 'dec' in d and 'fp' in d and f in kt]
    r = sorted(d['tong'] / kt[f] for f, d in co)
    g = sorted(a / b for a, b in giai if b > 5)
    print(f"Luot {j}: clip xong {len(co)}, MB {sum(kt[f] for f,_ in co):.0f}; tong s/MB trung vi {r[len(r)//2]:.2f} p90 {r[int(len(r)*.9)]:.2f}")
    print(f"   giai ma s/MB: n={len(g)} trung vi {g[len(g)//2]:.2f} p90 {g[int(len(g)*.9)]:.2f} max {g[-1]:.2f}; giai ma dai nhat {max(a for a,_ in giai):.0f}s")
    # theo moc 5 phut
    nhom = collections.defaultdict(list)
    for f, d in co:
        nhom[d['xong'].replace(minute=d['xong'].minute // 5 * 5, second=0)].append((d['tong'] / kt[f], kt[f]))
    for k in sorted(nhom):
        v = nhom[k]
        print(f"   {k:%H:%M}  clip {len(v):3d}  MB {sum(x[1] for x in v):6.0f}  s/MB tv {statistics.median(x[0] for x in v):5.2f}")
# Cung clip qua cac luot
a, b = kq['08:07'], kq['08:19']
chung = [f for f in a if 'tong' in a[f] and f in b and 'tong' in b[f]]
if chung:
    print('\nCung clip: luot 08:07 / luot 08:19 / luot 09:18')
    for f in chung[:12]:
        print(f"  {kt.get(f,0):6.1f} MB  {a[f]['tong']:6.1f}s  {b[f]['tong']:6.1f}s  {kq['09:18'].get(f,{}).get('tong',0):6.1f}s  {f[:44]}")
