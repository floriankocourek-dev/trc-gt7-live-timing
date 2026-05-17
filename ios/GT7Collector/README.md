# TRC GT7 Collector for iOS

Native iPhone collector prototype for the TRC GT7 Live Timing System.

## What it does

- Loads race entries from the existing live timing server.
- Lets the driver select race, entry, driver, team PIN and PlayStation IP.
- Registers as a collector with the backend.
- Sends GT7 heartbeat packets to the PlayStation.
- Receives GT7 UDP telemetry on port `33740`.
- Decrypts GT7 telemetry packets using Salsa20.
- Sends selected telemetry to `/api/collector/telemetry`.

## Important iOS limitations

- This must be a native app. A browser/PWA cannot receive GT7 UDP telemetry on iOS.
- Building/installing requires a Mac with Xcode.
- Distribution to other iPhones requires Apple Developer signing, TestFlight, Ad Hoc, or App Store distribution.
- iOS will show a Local Network permission prompt on first use.
- iPhone and PlayStation must be in the same local network.

## Build on Mac

Install XcodeGen:

```bash
brew install xcodegen
```

Generate the Xcode project:

```bash
cd ios/GT7Collector
xcodegen generate
open TRCGT7Collector.xcodeproj
```

In Xcode:

1. Select the `TRCGT7Collector` target.
2. Set your Apple Team under Signing & Capabilities.
3. Connect your iPhone.
4. Build and run.

## Default server

The app defaults to:

```text
https://trc-gt7-live-timing.onrender.com
```

## Status

This is a first native iOS implementation. It mirrors the Windows collector architecture, but it still needs a real-device validation pass because GT7 UDP behavior, iOS local network permissions, and signing can only be fully verified on an iPhone/Mac setup.
