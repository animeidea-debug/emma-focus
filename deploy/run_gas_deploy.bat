@echo off
rem ============================================================================
rem 🚀 Emma Focus — GAS 部署 (Windows 公司网络)
rem
rem 功能：通过公司代理推送 GAS 代码 + 自动创建版本 + 部署
rem
rem macOS 用户请使用：sh deploy/deploy_gas.sh
rem ============================================================================

set HTTPS_PROXY=http://proxy.sin.sap.corp:8080
set HTTP_PROXY=http://proxy.sin.sap.corp:8080

echo.
echo =============================================
echo   🚀 Emma Focus — GAS 部署
echo =============================================
echo   网络: 公司代理 (proxy.sin.sap.corp:8080)
echo.

cd /d %~dp0..\gas

echo 📤 推送代码到 Google Apps Script...
clasp push
if %ERRORLEVEL% neq 0 (
    echo ❌ clasp push 失败
    pause
    exit /b 1
)

echo.
echo 🏷️  创建版本标签...

REM Get current date for version description (YYYY-MM-DD format)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set VERSION_DESC=deploy-%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%

REM Create version and parse output
for /f "tokens=1" %%V in ('clasp version "%VERSION_DESC%" 2^>^&1 ^| findstr "Created"') do set VERSION_NUM=%%V
if "%VERSION_NUM%"=="" (
    echo ⚠️  无法创建版本号，跳过部署步骤
) else (
    echo 🚀 部署版本 %VERSION_NUM%...
    clasp deploy --versionNumber %VERSION_NUM%
)

echo.
echo =============================================
echo   ✅ GAS 部署完成！
echo =============================================
echo.
