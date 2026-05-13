--자동 bat 명령어

@echo off
rd /s /q build
rd /s /q dist
del app.spec
pyinstaller --onefile --clean ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "app/translations;app/translations" ^
  --add-data "translations;translations" ^
  --hidden-import flask_babel ^
  app.py
pause

--수동 단계
--2025.06.27
pyinstaller --onefile --clean --add-data "templates;templates" --add-data "static;static" --add-data "app/translations;app/translations" --add-data "translations;translations" --hidden-import flask_babel app.py 


--실행 및 test

--cd dist
--app.exe


--접속 http://localhost:7777