# Bộ cài ĐẦY ĐỦ TimClipPro cho một máy Windows MỚI (không cần cài Python / FFmpeg / Node trước, không cần mạng).
# Chạy qua CAI_DAT_TimClipPro.bat (nhấp đúp). File này nằm trong thư mục cai_dat\ của bộ cài đã giải nén.
#
# Làm theo thứ tự, lỗi ở bước nào thì DỪNG ở bước đó (chưa ghi gì vào máy trước bước 4):
#   1 máy 64-bit Windows 10+   2 mọi file của bộ cài khớp SHA256SUMS.txt   3 chỗ cài trống, đủ dung lượng, người dùng đồng ý
#   4 Python 3.12 xách tay (bản chính thức, giải nén từ MSI của python.org) → C:\TimClipPro_Python
#   5 FFmpeg + Node.js → C:\TimClipPro\tools\ffmpeg\bin (launcher tự đưa thư mục này vào PATH của ứng dụng)
#   6 bản phát hành ĐÃ KÝ → C:\TimClipPro_Feed\stable-X.Y.Z (nguồn cập nhật dạng thư mục, như PC2)
#   7 bootstrap.py của bộ kit (kiểm chữ ký, tạo môi trường riêng, cài bản Stable đầu tiên) — pip CHỈ đọc wheelhouse kèm theo
#   rồi lối tắt Desktop + doctor.
# Không chép kho vân tay, lịch sử, cookie, khoá Google / YouTube: mỗi máy tự làm sau khi cài.
param(
    [string]$Goc = 'C:\TimClipPro',
    [string]$State = 'C:\TimClipPro_State',
    [string]$Feed = 'C:\TimClipPro_Feed',
    [string]$PythonDir = 'C:\TimClipPro_Python',
    [switch]$KhongHoi,      # bộ thử: không hỏi đồng ý / không hỏi mở ứng dụng
    [switch]$KhongLoiTat    # bộ thử: không tạo lối tắt Desktop
)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Bo = $PSScriptRoot
$Gio = Get-Date -Format 'yyyyMMdd_HHmmss'

function Dung([string]$ly_do) {
    Write-Host ''
    Write-Host "[DỪNG] $ly_do" -ForegroundColor Red
    Write-Host 'Chưa cài xong. Sửa theo hướng dẫn ở trên rồi chạy lại CAI_DAT_TimClipPro.bat.' -ForegroundColor Red
    exit 1
}

function Buoc([string]$so, [string]$ten) { Write-Host ''; Write-Host "===== [$so/7] $ten =====" -ForegroundColor Cyan }

function Bam([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() }

function Chep-Thu-Muc([string]$nguon, [string]$dich) {
    New-Item -ItemType Directory -Force -Path $dich | Out-Null
    Copy-Item -Path (Join-Path $nguon '*') -Destination $dich -Recurse -Force
    Get-ChildItem -LiteralPath $dich -Recurse -File | Unblock-File
}

# ---------------------------------------------------------------------------------------------------------------------
Buoc 1 'Kiểm máy'
if (-not [Environment]::Is64BitOperatingSystem) { Dung 'Máy cần Windows 64-bit.' }
if ([Environment]::OSVersion.Version.Major -lt 10) { Dung 'Máy cần Windows 10 hoặc 11.' }
$tt_p = Join-Path $Bo 'thong_tin.json'
if (-not (Test-Path -LiteralPath $tt_p)) { Dung 'Thiếu cai_dat\thong_tin.json — hãy GIẢI NÉN TOÀN BỘ file ZIP ra một thư mục rồi chạy lại.' }
$tt = Get-Content -LiteralPath $tt_p -Raw -Encoding UTF8 | ConvertFrom-Json
$Ban = [string]$tt.phien_ban
if ($Ban -notmatch '^\d+\.\d+\.\d+$') { Dung 'thong_tin.json không hợp lệ.' }
Write-Host "Windows $([Environment]::OSVersion.Version) 64-bit — bộ cài TimClipPro $Ban (commit $($tt.commit.Substring(0, 12)))"

# ---------------------------------------------------------------------------------------------------------------------
Buoc 2 'Kiểm bộ cài (mã băm từng file)'
$tong_p = Join-Path $Bo 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $tong_p)) { Dung 'Thiếu cai_dat\SHA256SUMS.txt — hãy giải nén toàn bộ file ZIP.' }
$mong = @{}
foreach ($dong in Get-Content -LiteralPath $tong_p -Encoding UTF8) {
    if ($dong -match '^([0-9a-f]{64})  (.+)$') { $mong[$Matches[2]] = $Matches[1] }
}
if ($mong.Count -lt 10) { Dung 'SHA256SUMS.txt hỏng.' }
$sai = @()
$i = 0
foreach ($rel in $mong.Keys) {
    $i++
    if ($i % 50 -eq 0) { Write-Host "  đã kiểm $i/$($mong.Count) file..." }
    $p = Join-Path $Bo $rel
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { $sai += "THIẾU $rel"; continue }
    if ((Bam $p) -ne $mong[$rel]) { $sai += "SAI $rel" }
}
$thua = @(Get-ChildItem -LiteralPath $Bo -Recurse -File | ForEach-Object {
        $_.FullName.Substring($Bo.Length + 1).Replace('\', '/') } | Where-Object {
        $_ -ne 'SHA256SUMS.txt' -and -not $mong.ContainsKey($_) -and $_ -notlike '*__pycache__*' })
if ($sai.Count -gt 0) {
    $sai | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Dung "$($sai.Count) file thiếu hoặc bị hỏng khi chép — chép lại / giải nén lại file ZIP."
}
if ($thua.Count -gt 0) {
    $thua | Select-Object -First 10 | ForEach-Object { Write-Host "  THỪA $_" -ForegroundColor Red }
    Dung 'Bộ cài có file lạ — dùng đúng file ZIP gốc, giải nén vào thư mục TRỐNG.'
}
Write-Host "  $($mong.Count) file: KHỚP."
Get-ChildItem -LiteralPath $Bo -Recurse -File | Unblock-File

# ---------------------------------------------------------------------------------------------------------------------
Buoc 3 'Kiểm chỗ cài'
$Goc, $State, $Feed, $PythonDir = @($Goc, $State, $Feed, $PythonDir) | ForEach-Object { [IO.Path]::GetFullPath($_) }
if (Test-Path -LiteralPath (Join-Path $Goc 'launcher\launcher.json')) {
    Dung "Máy này ĐÃ cài TimClipPro ở $Goc. Muốn lên bản mới: dùng $Goc\CapNhat.bat theo ghi chú phát hành."
}
foreach ($p in @($Goc, $State, $Feed, $PythonDir)) {
    if ($p -match 'OneDrive|Dropbox|Google Drive') { Dung "$p nằm trong thư mục đồng bộ đám mây — chọn chỗ khác." }
}
$o = (Get-Item -LiteralPath ([IO.Path]::GetPathRoot($Goc))).PSDrive
$trong_gb = [math]::Round((Get-PSDrive -Name $o.Name).Free / 1GB, 1)
if ($trong_gb -lt 3) { Dung "Ổ $($o.Name): chỉ còn $trong_gb GB trống — cần ít nhất 3 GB." }
$feed_ban = Join-Path $Feed "stable-$Ban"
Write-Host "  Ứng dụng      : $Goc"
Write-Host "  Dữ liệu       : $State"
Write-Host "  Bản phát hành : $feed_ban"
Write-Host "  Python 3.12   : $PythonDir"
Write-Host "  Ổ $($o.Name): còn $trong_gb GB trống."
if (-not $KhongHoi) {
    Write-Host ''
    $tl = Read-Host 'Gõ C rồi Enter để CÀI (phím khác = thoát, chưa ghi gì vào máy)'
    if ($tl.Trim().ToUpper() -ne 'C') { Write-Host 'Đã thoát. Chưa ghi gì vào máy.'; exit 2 }
}

# ---------------------------------------------------------------------------------------------------------------------
Buoc 4 'Python 3.12 xách tay'
$py = Join-Path $PythonDir 'python.exe'
if (Test-Path -LiteralPath $py) {
    $mong_dll = $mong['python/python312.dll']
    $co_dll = Join-Path $PythonDir 'python312.dll'
    if (-not (Test-Path -LiteralPath $co_dll) -or (Bam $co_dll) -ne $mong_dll) {
        Dung "$PythonDir đã có một Python KHÁC — đổi tên/xoá thư mục đó hoặc báo người hỗ trợ."
    }
    Write-Host "  Đã có sẵn ở $PythonDir (đúng bản của bộ cài) — dùng lại."
} else {
    Chep-Thu-Muc (Join-Path $Bo 'python') $PythonDir
    Write-Host "  Đã chép Python vào $PythonDir."
}
$v = & $py -I -c "import sys, venv, ensurepip, ssl, sqlite3; print('%d.%d.%d' % sys.version_info[:3])"
if ($LASTEXITCODE -ne 0 -or $v -notlike '3.12.*') { Dung "Python ở $PythonDir không chạy được (kết quả: $v)." }
Write-Host "  Python $v chạy được."

# ---------------------------------------------------------------------------------------------------------------------
Buoc 5 'FFmpeg + Node.js'
$bin = Join-Path $Goc 'tools\ffmpeg\bin'
Chep-Thu-Muc (Join-Path $Bo 'ffmpeg') $bin
Copy-Item -LiteralPath (Join-Path $Bo 'node\node.exe') -Destination $bin -Force
Unblock-File -LiteralPath (Join-Path $bin 'node.exe')
foreach ($exe in 'ffmpeg', 'ffprobe') {
    # Đọc HẾT đầu ra rồi mới lấy dòng đầu: Select-Object -First 1 cắt ngang tiến trình → mã thoát sai.
    $ra = @(& (Join-Path $bin "$exe.exe") -hide_banner -version)
    if ($LASTEXITCODE -ne 0) { Dung "$exe.exe không chạy được." }
    Write-Host "  $($ra[0])"
}
$nv = & (Join-Path $bin 'node.exe') --version
if ($LASTEXITCODE -ne 0) { Dung 'node.exe không chạy được.' }
Write-Host "  Node.js $nv (dùng khi tải YouTube có cookie đăng nhập)"

# ---------------------------------------------------------------------------------------------------------------------
Buoc 6 "Bản phát hành $Ban (đã ký)"
$nguon_ban = Join-Path $Bo "feed\stable-$Ban"
if (Test-Path -LiteralPath $feed_ban) {
    foreach ($f in Get-ChildItem -LiteralPath $nguon_ban -File) {
        $q = Join-Path $feed_ban $f.Name
        if (-not (Test-Path -LiteralPath $q) -or (Bam $q) -ne (Bam $f.FullName)) {
            Dung "$feed_ban đã có nhưng KHÁC bản của bộ cài — xoá thư mục đó rồi chạy lại."
        }
    }
    Write-Host "  Đã có sẵn, giống từng byte — dùng lại."
} else {
    Chep-Thu-Muc $nguon_ban $feed_ban
    Write-Host "  Đã chép vào $feed_ban."
}

# ---------------------------------------------------------------------------------------------------------------------
Buoc 7 'Cài ứng dụng (kiểm chữ ký, tạo môi trường, cài bản đầu) — vài phút'
$kit = Join-Path $Bo 'kit'
$cu = @{}
foreach ($k in 'PIP_NO_INDEX', 'PIP_FIND_LINKS', 'PIP_DISABLE_PIP_VERSION_CHECK') { $cu[$k] = [Environment]::GetEnvironmentVariable($k) }
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = (Join-Path $Bo 'wheelhouse')
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
Push-Location -LiteralPath $kit
try {
    & $py -E -s -B bootstrap.py --goc $Goc --state $State --python-goc $py --tin-cay trusted_keys.json --nguon-thu-muc $Feed
    $rc = $LASTEXITCODE
} finally {
    Pop-Location
    foreach ($k in $cu.Keys) { [Environment]::SetEnvironmentVariable($k, $cu[$k]) }
}
if ($rc -ne 0) { Dung "bootstrap.py báo lỗi (mã $rc) — đọc dòng lỗi ở trên. Chạy lại file .bat sẽ làm tiếp phần còn dở." }
$bat = Join-Path $Goc 'TimClipPro.bat'
if (-not (Test-Path -LiteralPath $bat)) { Dung "Không thấy $bat sau khi cài." }

# ---------------------------------------------------------------------------------------------------------------------
Write-Host ''
Write-Host '===== Kiểm sau khi cài (doctor) =====' -ForegroundColor Cyan
& (Join-Path $Goc 'launcher\env\Scripts\python.exe') (Join-Path $Goc 'launcher\launcher.py') doctor
if (-not $KhongLoiTat) {
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'TimClipPro.lnk'
    $sh = New-Object -ComObject WScript.Shell
    $l = $sh.CreateShortcut($lnk)
    $l.TargetPath = $bat
    $l.WorkingDirectory = $Goc
    $l.Description = 'TimClipPro'
    $l.Save()
    Write-Host "Lối tắt Desktop: $lnk"
}
Write-Host ''
Write-Host "===== ĐÃ CÀI XONG TimClipPro $Ban =====" -ForegroundColor Green
Write-Host "Mở ứng dụng: icon «TimClipPro» trên Desktop (hoặc $bat) — trình duyệt mở http://localhost:8501"
Write-Host 'Việc tiếp theo (mỗi máy tự làm): dựng kho vân tay ở tab kho, đặt cookie YouTube, khoá Google / YouTube API (xem HUONG_DAN).'
Write-Host 'Thư mục bộ cài này có thể xoá sau khi ứng dụng mở được.'
if (-not $KhongHoi) {
    $mo = Read-Host 'Mở ứng dụng ngay? (C = có)'
    if ($mo.Trim().ToUpper() -eq 'C') { Start-Process -FilePath $bat -WorkingDirectory $Goc }
}
exit 0
