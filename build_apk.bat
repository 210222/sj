@echo off
echo === Coherence Coach APK Builder ===
echo.
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot
set ANDROID_HOME=C:\Users\21022\AppData\Local\Android\Sdk
set PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\platform-tools;%PATH%

echo JAVA_HOME=%JAVA_HOME%
echo ANDROID_HOME=%ANDROID_HOME%
echo.
echo Prerequisites:
echo   1. Node.js ^(npm^)
echo   2. JDK 21+ ^(winget install EclipseAdoptium.Temurin.21.JDK^)
echo   3. Android SDK at %%ANDROID_HOME%%
echo.

echo === Step 1: Install Capacitor ===
cd /d D:\Claudedaoy\coherence\frontend
call npm install @capacitor/core @capacitor/cli @capacitor/android --save

echo === Step 2: Build web frontend ===
call npm run build

echo === Step 3: Init Capacitor ^(skip if android/ exists^) ===
if not exist android (
    call npx cap init CoherenceCoach com.coherence.coach --web-dir=dist
    call npx cap add android
) else (
    echo android/ already exists, skipping init
)

echo === Step 4: Sync web assets ===
call npx cap sync

echo === Step 5: Build APK ===
cd android
call gradlew assembleRelease

echo.
echo === Done ===
echo.
echo ============================================
echo  IMPORTANT: Before building, edit this file:
echo    frontend/capacitor.config.json
echo  Change "url" to your backend server address:
echo    - Same PC:     http://127.0.0.1:8001
echo    - WiFi LAN:    http://192.168.x.x:8001
echo    - Cloud:       https://your-server.com
echo ============================================
echo.
echo APK location:
dir /s /b app\build\outputs\apk\release\*.apk 2>nul
if errorlevel 1 (
    echo APK not found. Check for errors above.
    echo Try debug build: cd android ^&^& gradlew assembleDebug
)
