# Collector Safety Notes

The collector is designed to be transparent and small.

It may:

- receive GT7 telemetry from the local network
- connect to the timing server
- store local settings
- write local troubleshooting logs

It must not:

- read personal files
- record keyboard input
- capture the screen
- use microphone or camera
- read browser, Discord, PSN or Steam data
- run invisibly in the background without user intent

User-facing wording:

```text
This app only reads GT7 telemetry from your local network and sends selected race telemetry to the timing server.

Sent data:
- lap number
- lap times
- car position
- speed
- fuel
- gear / RPM
- throttle / brake
- selected team / driver

Not accessed:
- personal files
- microphone
- camera
- keyboard input
- screen capture
- browser data
```

