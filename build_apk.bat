@echo off
set ANDROID_HOME=C:\Users\21022\AppData\Local\Android\Sdk
set PATH=%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\platform-tools;%PATH%

echo === Accepting licenses ===
echo y | %ANDROID_HOME%\cmdline-tools\latest\bin\sdkmanager.bat --licenses

echo === Building APK ===
cd /d D:\Claudedaoy\coherence\mobile
call flutter build apk --release

echo === Done ===
echo APK location:
dir /s /b build\app\outputs\flutter-apk\*.apk
