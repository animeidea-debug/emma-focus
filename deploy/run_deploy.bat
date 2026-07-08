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

"C:\Program Files\Git\bin\sh.exe" -c "cd /c/Users/I048299/Claude\ Projects/Emma\ Focus && WEBDAV_PASS='%RCLONE_PASS%' sh deploy/deploy.sh"
