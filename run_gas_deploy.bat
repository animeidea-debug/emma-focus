@echo off
set HTTPS_PROXY=http://proxy.sin.sap.corp:8080
set HTTP_PROXY=http://proxy.sin.sap.corp:8080

echo ===== Emma Focus - GAS Deployment =====
echo Pushing to Google Apps Script via corporate proxy...
echo.

clasp push

echo.
echo Done.