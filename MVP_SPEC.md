# MVP Specification

## MVP Objective

Create a working prototype for a GT7 endurance live timing system using mock telemetry first.

The MVP must allow:

1. Race Control to create an event.
2. Race Control to define whether the event is solo or team-based.
3. Race Control to set drivers per team if team event is selected.
4. Race Control to create entries with car number, team name, car model, class and drivers.
5. Race Control to generate team codes.
6. Mock collectors to register using race code, entry ID, team code and driver ID.
7. Mock collectors to send telemetry every second.
8. Public viewers to see live standings.
9. Teams to log in and see only their own private engineer data.
10. Race Control to monitor all collectors and apply penalties.

## MVP Public Standings Columns

- Position
- Car Number
- Class
- Team Name
- Current Driver
- Car Model
- Laps
- Gap to Leader
- Gap to Car Ahead
- Last Lap
- Best Lap
- Pit Status
- Pit Stops
- Penalty
- Status
- Connection Status

## MVP Team Engineer View

- Own car number
- Own team name
- Current driver
- Position
- Gap ahead
- Gap behind
- Current lap
- Last lap
- Best lap
- Fuel
- Estimated laps remaining
- Speed
- Gear
- RPM
- Throttle
- Brake
- Current stint
- Pit stops
- Connection status

## MVP Race Control View

- Race list
- Create race form
- Event type selector: Solo / Team
- Drivers per team field
- Entry creation form
- Team code generation
- Collector status table
- Standings table
- Penalty controls
- Manual status controls
- Race log

## MVP Collector

The collector should have:

- config file support
- command line mock mode
- simple GUI later
- registration with backend
- token-based telemetry sending
- reconnect logic
- readable error messages

## MVP Standings Logic

For first MVP:

- sort by laps descending
- if lap_progress exists, sort by total_progress
- otherwise sort by last update/lap data
- calculate basic gap if possible
- otherwise display `estimated` or null

## Later Enhancements

- real GT7 UDP telemetry source
- track reference lap
- lap progress calculation
- virtual sectors
- pitlane detection
- OBS overlay
- Windows installer
- signed executable

