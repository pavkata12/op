"""
Installation script for the kiosk client.
"""
import os
import sys
import ctypes
import winreg
import shutil
from pathlib import Path

def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def add_to_startup():
    """Add the client to Windows startup."""
    try:
        # Get the path to the client executable
        client_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "main.py"
        ))
        
        # Create startup registry key
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        
        # Add the client to startup
        winreg.SetValueEx(
            key,
            "KioskClient",
            0,
            winreg.REG_SZ,
            f'pythonw "{client_path}"'
        )
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Error adding to startup: {e}")
        return False

def install_dependencies():
    """Install required Python packages."""
    try:
        os.system("pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        return False

def create_shortcut():
    """Create a desktop shortcut for the client."""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Kiosk Client.lnk")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))}"'
        shortcut.WorkingDirectory = os.path.dirname(__file__)
        shortcut.save()
        
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

def main():
    """Main installation function."""
    if not is_admin():
        print("This script requires administrator privileges.")
        print("Please run the script as administrator.")
        sys.exit(1)
    
    print("Installing Kiosk Client...")
    
    # Install dependencies
    print("Installing dependencies...")
    if not install_dependencies():
        print("Failed to install dependencies.")
        sys.exit(1)
    
    # Add to startup
    print("Adding to startup...")
    if not add_to_startup():
        print("Failed to add to startup.")
        sys.exit(1)
    
    # Create shortcut
    print("Creating desktop shortcut...")
    if not create_shortcut():
        print("Failed to create shortcut.")
        sys.exit(1)
    
    print("Installation completed successfully!")
    print("The Kiosk Client will start automatically when you log in.")
    print("You can also start it manually from the desktop shortcut.")

if __name__ == "__main__":
    main() 