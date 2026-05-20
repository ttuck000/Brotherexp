# Brotherexp2 — PyInstaller onefile (app_entryB.py)
# 프로젝트 루트에서: .\build_app_entryB.ps1
#
# 원하시던 한 줄(CMD, 루트에서 실행) — app_entry.py → app_entryB.py 로 변경:
# pyinstaller --onefile --name Brotherexp2 --hidden-import=waitress --hidden-import=pyodbc --hidden-import=config ^
#   --add-data "templates;templates" --add-data "static;static" ^
#   --add-data "app/translations/ko.json;app/translations" ^
#   --add-data "app/translations/en.json;app/translations" ^
#   --add-data "app/translations/th.json;app/translations" ^
#   app_entryB.py

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot "venv312\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Error "venv312\Scripts\python.exe 가 없습니다."
}

& $venvPy -m pip install -q pyinstaller waitress

& $venvPy -m PyInstaller --noconfirm --clean --onefile --name Brotherexp2 `
    --hidden-import=waitress `
    --hidden-import=pyodbc `
    --hidden-import=config `
    --add-data "templates;templates" `
    --add-data "static;static" `
    --add-data "app/translations/ko.json;app/translations" `
    --add-data "app/translations/en.json;app/translations" `
    --add-data "app/translations/th.json;app/translations" `
    app_entryB.py

Write-Host "완료: dist\Brotherexp2.exe" -ForegroundColor Green
