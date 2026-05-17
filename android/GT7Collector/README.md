# TRC GT7 Collector for Android

Native Android collector prototype for the TRC GT7 Live Timing System.

## What it does

- Loads race entries from the existing live timing server.
- Lets the driver select race, entry, driver, team PIN and PlayStation IP.
- Registers as a collector with the backend.
- Sends GT7 heartbeat packets to the PlayStation.
- Receives GT7 UDP telemetry on port `33740`.
- Decrypts GT7 telemetry packets using Salsa20.
- Sends selected telemetry to `/api/collector/telemetry`.

## Important Android notes

- This must be a native app. A browser/PWA cannot reliably receive GT7 UDP telemetry.
- Phone and PlayStation must be in the same local network.
- The phone should stay awake while the app is collecting telemetry.
- No admin/root access is required.
- The app only requests network permissions.

## Build in Android Studio

1. Open Android Studio.
2. Open this folder:

```text
android/GT7Collector
```

3. Let Android Studio sync Gradle.
4. Connect an Android phone or start an emulator.
5. Build and run the `app` target.

## Build APK from command line

With Android Studio/Android SDK installed:

```bash
cd android/GT7Collector
gradlew assembleDebug
```

The debug APK will be created at:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## Default server

The app defaults to:

```text
https://trc-gt7-live-timing.onrender.com
```

## Distribution

For quick internal tests, you can install the debug APK manually on test phones.

For a clean driver download later, build a signed release APK/AAB in Android Studio and distribute it through one of these:

- Google Play Internal Testing
- Firebase App Distribution
- direct APK download from a trusted location

## Status

This is a first native Android implementation. It mirrors the Windows collector architecture, but it still needs a real-device validation pass because GT7 UDP behavior and Android vendor network restrictions can only be fully verified on real phones.
