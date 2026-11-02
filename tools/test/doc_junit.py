"""In số liệu junit: thu thập/đạt/bỏ qua/hỏng/lỗi, test hỏng, lý do bỏ qua (gộp theo lý do)."""
import collections
import sys
import xml.etree.ElementTree as ET

for duong_dan in sys.argv[1:]:
    goc = ET.parse(duong_dan).getroot()
    s = goc if goc.tag == "testsuite" else goc.find("testsuite")
    t, f, e, k = (int(s.get(x, 0)) for x in ("tests", "failures", "errors", "skipped"))
    print(f"{duong_dan.rsplit('/', 1)[-1]}: thu thap={t} dat={t - f - e - k} bo_qua={k} hong={f} loi={e} "
          f"thoi_gian={float(s.get('time', 0)):.0f}s")
    ly_do = collections.Counter()
    for c in s.iter("testcase"):
        for the in ("failure", "error"):
            x = c.find(the)
            if x is not None:
                print(f"  {the.upper()}: {c.get('classname')}::{c.get('name')} | {(x.get('message') or '')[:150]}")
        x = c.find("skipped")
        if x is not None:
            ly_do[f"{c.get('classname')}: {(x.get('message') or '')[:100]}"] += 1
    for ld, n in ly_do.most_common():
        print(f"  BO QUA x{n}: {ld}")
