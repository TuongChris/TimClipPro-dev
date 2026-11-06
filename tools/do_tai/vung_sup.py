# -*- coding: utf-8 -*-
import os, re, datetime as dt
L = r'C:\Dev\TimClipPro_DevState\output\fingerprint.log'
KHO = r'E:\Kho_Tool_Quet\Kho_Joe_Games'
tat = sorted(f for f in os.listdir(KHO) if f.endswith('.opus'))
print('Tong', len(tat))
print('--- Clip lon quanh vung sup (chi so | MB | gio am thanh)')
for i, f in enumerate(tat, 1):
    mb = os.path.getsize(os.path.join(KHO, f)) / 1e6
    if 270 <= i <= 400 and mb > 120:
        print(f'{i:4d} {mb:7.0f} MB {mb/0.008/3600:5.1f} gio  {f[:60]}')
print('--- 25 clip lon nhat ca kho')
top = sorted(enumerate(tat, 1), key=lambda x: -os.path.getsize(os.path.join(KHO, x[1])))[:25]
print(', '.join(f'#{i}:{os.path.getsize(os.path.join(KHO, f))/1e6/0.008/3600:.1f}h' for i, f in top))
# Dong thoi gian luot 09:18 tu 09:33
J = '5363093045530188980'
re_f = re.compile(r"file=(?:'([^']*)'|\"([^\"]*)\")")
print('--- Luot 09:18: clip xu ly tu 09:33 (bat dau -> ket thuc)')
bd = {}
for dong in open(L, encoding='utf-8', errors='replace'):
    if J not in dong or 'event=clip' not in dong:
        continue
    t = dong[11:19]
    m = re_f.search(dong)
    f = (m.group(1) or m.group(2)) if m else ''
    if 'clip start' in dong:
        bd[f] = t
    elif t >= '09:33:00' and ('clip success' in dong or 'clip failed' in dong):
        e = re.search(r'elapsed=([0-9.]+)s', dong)
        mb = os.path.getsize(os.path.join(KHO, f)) / 1e6 if f in tat else 0
        tt = 'OK ' if 'success' in dong else 'LOI'
        if float(e.group(1)) > 60 or tt == 'LOI':
            print(f"  {tt} {bd.get(f,'?')} -> {t}  {float(e.group(1)):6.0f}s  {mb:6.0f} MB  {mb/0.008/3600:5.1f}h  {f[:44]}")
dang = [f for f in bd if f and J]
print('--- Clip da bat dau ma chua xong khi Dung (09:56):')
xong = set()
for dong in open(L, encoding='utf-8', errors='replace'):
    if J in dong and ('clip success' in dong or 'clip failed' in dong):
        m = re_f.search(dong)
        if m:
            xong.add(m.group(1) or m.group(2))
for f, t in bd.items():
    if f not in xong:
        mb = os.path.getsize(os.path.join(KHO, f)) / 1e6 if f in tat else 0
        print(f"  bat dau {t}  {mb:6.0f} MB {mb/0.008/3600:5.1f}h  {f[:50]}")
