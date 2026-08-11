@echo off
chcp 65001 >nul
setlocal
set "APP_DIR=%~dp0"

if not exist "%APP_DIR%osu-BiliRequest.exe" (
  echo Missing osu-BiliRequest.exe. Please extract the complete ZIP package.
  pause
  exit /b 3
)

if not exist "%APP_DIR%config.json" (
  "%APP_DIR%osu-BiliRequest.exe" --setup --config "%APP_DIR%config.json"
  if errorlevel 1 (
    pause
    exit /b 2
  )
)

"%APP_DIR%osu-BiliRequest.exe" --config "%APP_DIR%config.json" %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

if not "%APP_EXIT_CODE%"=="0" pause
exit /b %APP_EXIT_CODE%
