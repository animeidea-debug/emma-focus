@echo off
set HTTPS_PROXY=http://proxy.sin.sap.corp:8080
set HTTP_PROXY=http://proxy.sin.sap.corp:8080

echo ===== Emma Focus - GAS Deployment =====
echo Pushing to Google Apps Script via corporate proxy...
echo.

clasp push

REM Get current date for version description (YYYYMMDD format)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set VERSION_DESC=deploy-%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%

REM Create version and get version number
for /f "tokens=1" %%V in ('clasp version "%VERSION_DESC%" 2^>^&1 ^| findstr "Created"') do set VERSION_NUM=%%V
if "%VERSION_NUM%"=="" (
    echo Warning: Could not create version, skipping deploy step
) else (
    echo Deploying version %VERSION_NUM%...
    clasp deploy --versionNumber %VERSION_NUM%
)

echo.
echo Done.
