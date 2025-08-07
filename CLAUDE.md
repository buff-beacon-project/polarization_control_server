# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a polarization control server for a quantum optics Bell test experiment. The system controls waveplates and Pockels cells to manage light polarization across different stations (Alice, Bob, Source).

### Core Components

- **PolarizationServer**: Main ZMQ-based service that handles REST API and ZMQ requests
- **MotorController**: Threaded client for controlling Thorlabs APT motors via ZMQ
- **beacon_bridge_optimizations**: Optimization algorithms with file-based caching for Jones matrix calculations
- **redis_read**: Redis integration for storing/reading count data from experiment

### Service Architecture

The server uses the `ZMQServiceBase` from the `zmqhelpers` library, providing:
- ZMQ REQ/REP socket for commands
- HTTP server for health checks (`/healthz`) and metrics (`/metrics`)
- Integration with Redis for data persistence
- Optional Loki logging integration

### Configuration

All configuration is stored in `config/polarization.yaml`:
- Motor server endpoints (Alice, Bob, Source stations)
- Pockels cell Jones matrices and calibration parameters
- Polarization settings for different experiment modes
- Service ports and external service endpoints

### Commands Configuration

All available commands are documented in `src/commands.yaml`:
- Complete command definitions with descriptions
- Parameter specifications for each command
- Includes both original and newly implemented commands
- Used by the `commands` API endpoint to return available commands

### Caching System

The system uses a sophisticated caching mechanism in `beacon_bridge_optimizations.py`:
- File-based pickle caching with MD5 hash keys
- Cache control via `use_cache` and `update_cache` parameters
- Compensates for birefringence in Pockels cells

## Development Commands

### Running the Server
```bash
# Run directly
python3 src/polarization_server.py

# Run with Docker Compose
docker-compose up polarization_server

# Build Docker image
docker build -t polarization_server .
```

### Testing
```bash
# Run tests
python3 src/test_polarization_server.py
```

### Dependencies
```bash
# Install dependencies
pip install -r requirements.txt
```

## Key APIs

### Command Structure
Commands are sent as JSON: `{'cmd': 'command_name', 'params': {optional_parameters}}`

### Important Commands
- `set_polarization`: Set waveplates for specific experiment path
- `set_pc_to_bell_angles`: Control Pockels cells for Bell test angles
- `calibrate`: Calibrate waveplates for Alice, Bob, or Source
- `home`: Home Pockels cells
- `get_paths`: List all valid polarization settings
- `commands`: Get all available commands

### New Motor Control Commands
- `get_motor_info`: Get motor server info and waveplate names for each party
- `forward`: Move specific waveplate forward by position (`party`, `waveplate`, `position`)
- `backward`: Move specific waveplate backward by position (`party`, `waveplate`, `position`) 
- `goto`: Move specific waveplate to absolute position (`party`, `waveplate`, `position`)
- `positions`: Get current positions of all waveplates for all motors
- `get_current_path`: Return the currently active polarization path

### Caching Parameters
Most commands support:
- `use_cache`: bool - Use cached optimization results (default: true)
- `update_cache`: bool - Update cache with new results (default: false)

## File Structure
- `src/polarization_server.py`: Main server implementation
- `src/thorlabs_apt_motor_controller.py`: Motor control client
- `src/beacon_bridge_optimizations.py`: Optimization algorithms with caching
- `src/commands.yaml`: Command definitions and documentation
- `config/polarization.yaml`: Main configuration file
- `cache/`: Optimization result cache files
- `logs/`: Server logs

## Implemented New Features

### New Motor Control Commands (✅ Implemented)

#### Command 1: `get_motor_info` 
**Purpose**: Retrieve motor object names and waveplate names for each party
- Add new method `get_motor_info()` that connects to each motor server and retrieves `id_dict`
- Returns: `{"alice": {"names": [...], "ip": "...", "port": ...}, "bob": {...}, "source": {...}}`

#### Command 2: `forward`
**Purpose**: Move specific waveplate forward by given position
- Extract params: `party`, `waveplate`, `position`
- Call `mc.forward(waveplate, position)` on appropriate MotorController
- Returns structured response: `{'party': party, 'waveplate': waveplate, 'position': current_pos}`
- Example: `{'cmd': 'forward', 'params': {'party': 'alice', 'waveplate': 'alice_qwp_1', 'position': 43.0}}`

#### Command 3: `backward`  
**Purpose**: Move specific waveplate backward by given position
- Same structure as forward but call `mc.backward(waveplate, position)`
- Extract same params: `party`, `waveplate`, `position`
- Returns structured response with current position after movement

#### Command 4: `goto` (✅ New)
**Purpose**: Move specific waveplate to absolute position
- Extract params: `party`, `waveplate`, `position`
- Call `mc.goto(waveplate, position)` on appropriate MotorController
- Returns structured response with current position after movement
- Example: `{'cmd': 'goto', 'params': {'party': 'source', 'waveplate': 'alice_HWP_1', 'position': 45.0}}`

#### Command 5: `positions`
**Purpose**: Get current positions of all waveplates for all motors
- Create method `get_all_positions()` that calls `mc.getAllPos()` for each motor
- Returns: `{"alice": {"waveplate1": position, ...}, "bob": {...}, "source": {...}}`

### Path Tracking System (✅ Implemented)

#### Command 6: `get_current_path`
**Purpose**: Return the currently active polarization path
- Returns the stored `self.current_path` variable

#### Path Tracking Implementation:
1. **Add Instance Variable**: 
   - Add `self.current_path = None` in `__init__()` method

2. **Modify `set_polarization` Command Handler**:
   - When `cmd == "set_polarization"` is processed (line ~90), save the setting
   - Add `self.current_path = setting` after extracting the setting parameter
   - Log path changes: `self.logger.info(f"Current polarization path set to: {setting}")`

3. **Startup Path Recovery**:
   - Add new method `load_last_path_from_logs()` 
   - Search through log files in reverse chronological order for "Current polarization path set to:" entries
   - Extract the most recent path setting and set `self.current_path`
   - Call this method during `__init__()` after logger setup

4. **Log File Parsing**:
   - Read log files from `logs/` directory 
   - Look for pattern: "Current polarization path set to: {path_name}"
   - Use most recent entry as the startup path value
   - Handle cases where no previous path exists (set to None)

### Implementation Notes:
- Add all command handlers in `handle_request()` method around line 175
- Follow existing error handling patterns for motor connections
- Use consistent logging with `self.logger.info()` for all operations
- Maintain JSON response format matching existing commands
- Handle edge cases: missing log files, corrupted log entries, disconnected motors