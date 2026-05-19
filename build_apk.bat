@echo off
echo === Coherence Coach APK Builder (Direct) ===
echo.
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot
set ANDROID_HOME=C:\Users\21022\AppData\Local\Android\Sdk
set PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\platform-tools;%PATH%

REM 强制不走代理
set http_proxy=
set https_proxy=
set HTTP_PROXY=
set HTTPS_PROXY=

echo JAVA_HOME=%JAVA_HOME%
echo ANDROID_HOME=%ANDROID_HOME%
echo Proxy: DISABLED
echo.

echo === Step 1: Build web frontend ===
cd /d D:\Claudedaoy\coherence\frontend
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed
    pause
    exit /b 1
)

echo === Step 2: Sync web assets to Android ===
call npx cap sync
if errorlevel 1 (
    echo ERROR: Capacitor sync failed
    pause
    exit /b 1
)

echo === Step 3: Build APK (Release) ===
cd android
call .\gradlew assembleRelease
if errorlevel 1 (
    echo.
    echo Release build failed, trying debug build...
    call .\gradlew assembleDebug
)

echo.
echo === Done ===
echo APK location:
dir /s /b app\build\outputs\apk\release\*.apk 2>nul
dir /s /b app\build\outputs\apk\debug\*.apk 2>nul
