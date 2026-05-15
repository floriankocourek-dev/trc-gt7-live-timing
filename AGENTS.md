# TRC GT7 Live Timing Project

## Goal

Build an MVP web-based live timing and race control system for Gran Turismo 7 endurance races.

The system consists of:

- a simple collector app per driver/team
- a central backend server
- a public live timing website
- a private team engineer view
- a race control/admin interface

## Core Principles

1. The collector app must be extremely simple for non-technical users.
2. Public timing must only expose data that would be visible in real motorsport.
3. Private telemetry such as fuel, throttle, brake, RPM and detailed car data must only be visible to the owning team and Race Control.
4. Race Control can see and manage everything.
5. Do not require code changes for each event. Events must be configurable in the Race Control UI.
6. Start with mock telemetry before implementing real GT7 UDP telemetry.
7. Keep the collector small and safe. It should only read GT7 telemetry and send selected data to the timing server.

## MVP Technology

- Backend: FastAPI
- Database: SQLite for MVP
- Frontend: React
- Live updates: WebSocket
- Collector: Python
- Later: package collector as Windows .exe

## Required Roles

- Public Viewer
- Team
- Race Control
- Admin
- Stream

## Public Timing Fields

Public endpoints may expose:

- position
- car number
- class
- team name
- current driver
- car model
- laps completed
- gap to leader
- gap to car ahead
- last lap
- best lap
- pit status
- pit stops
- penalties
- race status
- connection status

Public endpoints must NOT expose:

- fuel
- fuel per lap
- estimated laps remaining
- throttle
- brake
- gear
- RPM
- tyre temperatures
- raw telemetry
- exact driver inputs

## Private Team Fields

Team-private endpoints may expose only for the authenticated team's own entry:

- fuel
- fuel per lap
- estimated laps remaining
- speed
- gear
- RPM
- throttle
- brake
- own position data
- own stint data
- own connection status

## Race Control

Race Control must be able to:

- create races
- select solo or team event
- define drivers per team
- create entries
- generate team codes
- assign drivers
- monitor collectors
- view all standings
- view all private telemetry
- add penalties
- make manual corrections
- start/stop the race
- view race log

## Collector App UX

The collector app must show only:

- Race Code
- Team selection
- Driver selection
- PS5 IP / auto-detect
- Start / Stop
- GT7 connection status
- Server connection status
- Sending status

Avoid technical terms in the UI.

## Security

- No admin rights required for the collector.
- Do not access personal files, keyboard input, microphone, camera, browser data or screen capture.
- Use team code only for login/registration.
- Use temporary tokens for telemetry sending.
- Enforce permissions server-side.
- Never send private data through public endpoints.
- Logs must not contain secret team codes or raw tokens.

## Development Order

1. Create backend data models and APIs.
2. Create mock collector.
3. Create public standings page.
4. Create team login and private team page.
5. Create race control page.
6. Add WebSocket live updates.
7. Add basic standings calculation.
8. Add GT7 telemetry source later.
9. Package collector for Windows later.

## Out of Scope for MVP

- Weather radar
- Mobile app
- Perfect gap calculation
- Perfect pit detection
- Fully polished stream overlay
- iOS/Android collector

