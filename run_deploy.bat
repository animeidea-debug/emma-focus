@echo off
set PATH=%USERPROFILE%\Downloads\rclone\rclone-v1.74.3-windows-amd64;%PATH%
set RCLONE_PASS=%WEBDAV_PASS%
if "%RCLONE_PASS%"=="" (
    echo [ERROR] WEBDAV_PASS not set.
    echo Run: setx WEBDAV_PASS "your-password"
    echo Then restart your terminal.
    pause
    exit /b 1
)

echo Configuring rclone...
rclone config delete emma-focus-ip 2>nul
rclone config delete emma-focus-ts 2>nul
rclone config create emma-focus-ip webdav url "http://192.168.6.108:8889" vendor other user garychen pass %RCLONE_PASS% >nul 2>&1
rclone config create emma-focus-ts webdav url "https://z4pro-xxel.tail1a5bb9.ts.net/" vendor other user garychen pass %RCLONE_PASS% >nul 2>&1

"C:\Program Files\Git\bin\sh.exe" -c "cd /c/Users/I048299/Claude\ Projects/Emma\ Focus && sh ./deploy.sh"
