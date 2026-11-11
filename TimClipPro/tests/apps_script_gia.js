'use strict';
// Google Sheet GIẢ cho test Apps Script (chạy bằng Node, không gọi Google). Dùng:
//   node apps_script_gia.js <file .gs> <file thân test .js>
// Thân test là thân một hàm, chạy CÙNG phạm vi với mã .gs (thấy được const cấp cao nhất), có sẵn:
//   taoSheet(ten, hang, soHangToiDa), ss, ui (ui.khi = function(tieuDe, noiDung, nut) { return 'YES' | 'OK' | ... }).
// Hàm trả về một giá trị JSON → in ra stdout. Chỉ giả lập phần API mà các hàm được test dùng tới; getRange ngoài
// lưới ném lỗi như Apps Script thật («The coordinates of the range are outside the dimensions of the sheet.»).
const fs = require('fs');
const vm = require('vm');

function chuoiRong(x) { return x === '' || x === null || x === undefined; }

// Mọi hàm định dạng không mô phỏng (setWrap, setBorder…) trả về chính đối tượng để gọi nối tiếp.
function boc(doiTuong) {
  return new Proxy(doiTuong, {
    get(dich, ten) {
      if (ten in dich) return dich[ten];
      if (typeof ten === 'string' && /^(set|clear|auto|insert|delete|hide|show|protect|activate)/.test(ten)) {
        return function () { return this; };
      }
      return undefined;
    }
  });
}

class Vung {
  constructor(sheet, r, c, nr, nc) { this.sheet = sheet; this.r = r; this.c = c; this.nr = nr; this.nc = nc; }
  _bang(lay) {
    const ra = [];
    for (let i = 0; i < this.nr; i++) {
      const dong = [];
      for (let j = 0; j < this.nc; j++) dong.push(lay(this.sheet._o(this.r + i, this.c + j)));
      ra.push(dong);
    }
    return ra;
  }
  _ghi(bang, gan) {
    if (bang.length !== this.nr || bang.some(d => d.length !== this.nc)) {
      throw new Error('The number of rows or columns in the data does not match the range.');
    }
    bang.forEach((d, i) => d.forEach((x, j) => gan(this.sheet._o(this.r + i, this.c + j), x)));
    return this;
  }
  getRow() { return this.r; }
  getColumn() { return this.c; }
  getLastRow() { return this.r + this.nr - 1; }
  getNumRows() { return this.nr; }
  getNumColumns() { return this.nc; }
  getValues() { return this._bang(o => o.v); }
  getValue() { return this.getValues()[0][0]; }
  getDisplayValues() { return this._bang(o => (o.hien !== undefined ? o.hien : (chuoiRong(o.v) ? '' : String(o.v)))); }
  getFormulas() { return this._bang(o => o.f || ''); }
  setValues(bang) {
    return this._ghi(bang, (o, x) => {
      delete o.hien;
      if (typeof x === 'string' && x.charAt(0) === '=') { o.f = x; o.v = ''; } else { o.f = ''; o.v = x; }
    });
  }
  setValue(x) { return this.setValues([[x]]); }
  clearContent() { return this._ghi(this._bang(() => ''), o => { o.v = ''; o.f = ''; delete o.hien; }); }
  getBackgrounds() { return this._bang(o => o.nen || '#ffffff'); }
  setBackgrounds(b) { return this._ghi(b, (o, x) => { o.nen = x; }); }
  getFontColors() { return this._bang(o => o.chu || '#000000'); }
  setFontColors(b) { return this._ghi(b, (o, x) => { o.chu = x; }); }
  getFontWeights() { return this._bang(o => o.dam || 'normal'); }
  setFontWeights(b) { return this._ghi(b, (o, x) => { o.dam = x; }); }
  setDataValidation(quyTac) { this.sheet.kiemTra.push({ hang: this.r, cot: this.c, soHang: this.nr, quyTac }); return this; }
}

class TrangTinh {
  constructor(ten, hang, soHangToiDa) {
    this.ten = ten;
    this.o = new Map();
    this.kiemTra = [];
    (hang || []).forEach((d, i) => d.forEach((x, j) => {
      const o = this._o(i + 1, j + 1);
      if (x && typeof x === 'object' && !(x instanceof Date)) Object.assign(o, x); else o.v = x;
    }));
    this.soHang = Math.max(soHangToiDa || 1000, (hang || []).length);
    this.soCot = 50;
  }
  _o(r, c) {
    const k = r + ',' + c;
    if (!this.o.has(k)) this.o.set(k, { v: '', f: '' });
    return this.o.get(k);
  }
  _co(o) { return !chuoiRong(o.v) || !!o.f; }
  getName() { return this.ten; }
  getConditionalFormatRules() { return []; }
  getMaxRows() { return this.soHang; }
  getMaxColumns() { return this.soCot; }
  getLastRow() { let m = 0; for (const [k, o] of this.o) if (this._co(o)) m = Math.max(m, +k.split(',')[0]); return m; }
  getLastColumn() { let m = 0; for (const [k, o] of this.o) if (this._co(o)) m = Math.max(m, +k.split(',')[1]); return m; }
  getRange(r, c, nr, nc) {
    nr = nr === undefined ? 1 : nr; nc = nc === undefined ? 1 : nc;
    if (r < 1 || c < 1 || nr < 1 || nc < 1 || r + nr - 1 > this.soHang || c + nc - 1 > this.soCot) {
      throw new Error('The coordinates of the range are outside the dimensions of the sheet.');
    }
    return boc(new Vung(this, r, c, nr, nc));
  }
  _doiHang(tu, so) {
    const moi = new Map();
    for (const [k, o] of this.o) {
      const [r, c] = k.split(',').map(Number);
      moi.set((r >= tu ? r + so : r) + ',' + c, o);
    }
    this.o = moi;
    this.soHang += so;
  }
  insertRowBefore(r) { this._doiHang(r, 1); return this; }
  insertRowsBefore(r, so) { this._doiHang(r, so); return this; }
  insertRowsAfter(r, so) { this._doiHang(r + 1, so); return this; }
  // Ô thật để test đọc lại: { v, f, nen, ... }.
  o_(r, c) { return this._o(r, c); }
}

function taoMoiTruong() {
  const props = new Map();
  const sheets = [];
  const ui = {
    thongBao: [],
    khi: null,
    ButtonSet: { OK: 'OK', YES_NO: 'YES_NO', OK_CANCEL: 'OK_CANCEL' },
    Button: { YES: 'YES', NO: 'NO', OK: 'OK', CANCEL: 'CANCEL' },
    alert(tieuDe, noiDung, nut) {
      this.thongBao.push([tieuDe, noiDung === undefined ? '' : noiDung]);
      return this.khi ? this.khi(tieuDe, noiDung, nut) : 'YES';
    }
  };
  const ss = boc({
    hoatDong: null,
    vungChon: null,
    getSheetByName(ten) { return sheets.find(s => s.ten === ten) || null; },
    insertSheet(ten) { const s = boc(new TrangTinh(ten, [], 1000)); sheets.push(s); return s; },
    getSheets() { return sheets.slice(); },
    getActiveSheet() { return this.hoatDong; },
    getActiveRange() { return this.vungChon; },
    getSpreadsheetTimeZone() { return 'Asia/Ho_Chi_Minh'; },
    toast() {}
  });
  // newDataValidation(): mọi hàm dựng (requireValueInList, setAllowInvalid…) nối tiếp; build() trả quy tắc.
  const xayKiemTra = new Proxy({}, { get: (_, ten) => (ten === 'build' ? () => ({ quyTac: 'danh_sach' }) : () => xayKiemTra) });
  const g = {
    console,
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ss, getActive: () => ss, getUi: () => ui, flush() {},
      newDataValidation: () => xayKiemTra
    },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, waitLock() {}, releaseLock() {}, hasLock: () => true }) },
    PropertiesService: {
      getDocumentProperties: () => ({
        getProperty: k => (props.has(k) ? props.get(k) : null),
        setProperty: (k, v) => { props.set(k, String(v)); },
        deleteProperty: k => { props.delete(k); }
      })
    },
    Session: { getScriptTimeZone: () => 'Asia/Ho_Chi_Minh' },
    Utilities: { formatDate: d => new Date(d).toISOString() },
    Logger: { log() {} },
    taoSheet(ten, hang, soHangToiDa) { const s = boc(new TrangTinh(ten, hang, soHangToiDa)); sheets.push(s); return s; },
    ss,
    ui
  };
  return g;
}

const [fileGs, fileThan] = process.argv.slice(2);
const ma = fs.readFileSync(fileGs, 'utf8') + '\n;globalThis.__ket_qua = (function () {\n'
  + fs.readFileSync(fileThan, 'utf8') + '\n})();\n';
const g = taoMoiTruong();
vm.createContext(g);
vm.runInContext(ma, g, { filename: 'apps_script_test.js' });
process.stdout.write(JSON.stringify(g.__ket_qua === undefined ? null : g.__ket_qua));
