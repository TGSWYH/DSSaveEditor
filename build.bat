@echo off
REM ============================================================
REM  DSSaveEditor 构建脚本 (PyInstaller onefile)
REM  产物: dist\DSSaveEditor.exe (单文件, 双击运行)
REM  要求: pip install pyinstaller
REM ============================================================
cd /d "%~dp0"

echo [1/3] 清理旧构建产物...
if exist build rmdir /s /q build
if exist dist\DSSaveEditor.exe del /q dist\DSSaveEditor.exe

echo [2/3] PyInstaller 打包 (onefile, windowed)...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "DSSaveEditor" ^
  --icon "app.ico" ^
  --add-data "data;data" ^
  --add-data "app/locales;app/locales" ^
  run_editor.py

if errorlevel 1 (
    echo.
    echo [失败] 打包出错, 请查看上方日志
    pause
    exit /b 1
)

echo.
echo [3/3] 构建完成: dist\DSSaveEditor.exe
echo        - 单文件, 双击即用
echo        - 配置/备份会保存在 exe 同目录 (config.json / *.db.backup_*)
echo        - 首次启动会稍微慢 (自解压运行库), 属正常现象
pause
