@echo off
echo === Coherence Coach APK Builder ===
echo.
echo Prerequisites:
echo   1. Node.js (npm)
echo   2. JDK 21+ (winget install EclipseAdoptium.Temurin.21.JDK)
echo   3. Android SDK at %%ANDROID_HOME%%
echo.
set ANDROID_HOME=C:\Users\21022\AppData\Local\Android\Sdk
set PATH=%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\platform-tools;%PATH%

echo === Step 1: Install Capacitor ===
cd /d D:\Claudedaoy\coherence\frontend
call npm install @capacitor/core @capacitor/cli @capacitor/android --save 2>&1

echo === Step 2: Build web frontend ===
call npm run build

echo === Step 3: Init Capacitor ===
call npx cap init CoherenceCoach com.coherence.coach --web-dir=dist

echo === Step 4: Add Android platform ===
call npx cap add android

echo === Step 5: Sync web assets ===
call npx cap sync

echo === Step 6: Build APK ===
cd android
call gradlew assembleRelease

echo === Done ===
dir /s /b app\build\outputs\apk\release\*.apk
