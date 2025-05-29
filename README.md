# Kiosk Client-Server System

A secure kiosk management system for Windows computers, designed for public spaces like gaming centers and libraries.

## Features

### Server (Admin Panel)
- Manage multiple client computers
- Control sessions (start, pause, resume, end)
- Configure allowed applications
- Monitor client status and activity
- Remote maintenance capabilities

### Client (Kiosk Mode)
- Secure, locked-down environment
- Custom desktop with allowed applications
- Fake toolbar for window management
- Session timer and controls
- System shortcut blocking
- Graceful network disconnect handling

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure the server:
   - Copy `.env.example` to `.env`
   - Update configuration values
4. Run the server:
   ```bash
   python server/main.py
   ```
5. Install the client:
   - Run `client/install.py` as administrator
   - Follow the installation prompts

## Security

- Requires administrator privileges for client installation
- Secure network communication
- Prevents access to system tools
- Blocks system shortcuts
- Session management and timeout controls

## Development

### Project Structure
```
kiosk-system/
├── server/
│   ├── main.py
│   ├── admin_panel.py
│   ├── client_manager.py
│   └── utils/
├── client/
│   ├── main.py
│   ├── kiosk_desktop.py
│   ├── fake_toolbar.py
│   └── utils/
├── shared/
│   ├── protocol.py
│   └── constants.py
└── requirements.txt
```

## License

MIT License 