@echo off
chcp 65001 >nul
setlocal
set "APP_DIR=%~dp0"

if not exist "%APP_DIR%osu-BiliRequest.exe" (
  echo Missing osu-BiliRequest.exe. Please extract the complete ZIP package.
  pause
  exit /b 3
)

"%APP_DIR%osu-BiliRequest.exe" --setup --config "%APP_DIR%config.json"
pause
