"""Main application entry point for Binance Full Deposit History Tool."""
import sys
import traceback
import subprocess
from pathlib import Path


def setup_application():
    """Set up the Qt application with proper styling."""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("Binance Full Deposit History Tool")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Binance Tracker")
    
    # Enable high DPI support (automatically handled in Qt 6+)
    
    return app


def show_error_dialog(title: str, message: str, details: str = None):
    """Show error dialog to user."""
    try:
        from PySide6.QtWidgets import QMessageBox
        
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Critical)
        error_box.setWindowTitle(title)
        error_box.setText(message)
        
        if details:
            error_box.setDetailedText(details)
        
        error_box.exec()
    except ImportError:
        # Fallback to console output if Qt is not available
        print(f"ERROR: {title}")
        print(f"Message: {message}")
        if details:
            print(f"Details: {details}")


def check_and_install_dependencies():
    """Check if all required dependencies are installed, install if missing."""
    print("🔍 Checking dependencies...")
    
    required_packages = {
        'httpx': 'httpx>=0.25.0',
        'PySide6': 'PySide6>=6.6.0',
        'pydantic': 'pydantic>=2.5.0',
        'dotenv': 'python-dotenv>=1.0.0',
        'tenacity': 'tenacity>=8.2.0',
        'dateutil': 'python-dateutil>=2.8.0',
        'pyqtgraph': 'pyqtgraph>=0.13.0',
        'numpy': 'numpy>=1.24.0'
    }
    
    missing_packages = []
    
    for import_name, package_spec in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_spec)
    
    if missing_packages:
        print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
        print("🔧 Installing missing dependencies...")
        
        try:
            # Install missing packages
            cmd = [sys.executable, '-m', 'pip', 'install'] + missing_packages
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ All dependencies installed successfully!")
                return True
            else:
                print(f"❌ Failed to install dependencies: {result.stderr}")
                print("Please manually run: pip install -r requirements.txt")
                return False
                
        except Exception as e:
            print(f"❌ Error installing dependencies: {e}")
            print("Please manually run: pip install -r requirements.txt")
            return False
    else:
        print("✅ All dependencies are available.")
        return True

def show_startup_info():
    """Show application startup information."""
    print("" + "="*60)
    print("📈 Binance Full Deposit History Tool v1.0")
    print("" + "="*60)
    print(f"🐍 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"📂 Working Directory: {Path.cwd()}")


def main():
    """Main application entry point."""
    # Show startup info
    show_startup_info()
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required. You have {sys.version}")
        print("Please upgrade Python and try again.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Check and install dependencies
    if not check_and_install_dependencies():
        print("❌ Could not install required dependencies.")
        print("Please manually run: pip install -r requirements.txt")
        input("Press Enter to exit...")
        sys.exit(1)
    
    print("🚀 Starting application...")
    
    # Import after dependency check
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt
        from core.config import load_config, set_config
        from core.json_data_manager import JSONDataManager
        from ui.main_window import MainWindow
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please try: pip install -r requirements.txt")
        input("Press Enter to exit...")
        sys.exit(1)
    
    app = setup_application()
    
    try:
        
        # Determine application directory
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            app_dir = Path(sys.executable).parent
        else:
            # Running as Python script
            app_dir = Path(__file__).parent
        
        # Try to load configuration
        try:
            config = load_config(app_dir)
            set_config(config)
        except ValueError as e:
            # Config error (missing API keys) - let user configure in UI
            if "BINANCE_API_KEY" in str(e):
                # Create minimal config for UI setup
                config = None
            else:
                raise e
        
        # Initialize JSON data manager
        data_dir = app_dir / "data"
        data_dir.mkdir(exist_ok=True)
        data_manager = JSONDataManager(data_dir)
        
        # Create and show main window
        main_window = MainWindow(data_manager, app_dir)
        main_window.show()
        
        # If no config, prompt user to configure API keys
        if not config:
            main_window.show_settings_dialog(required=True)
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        error_details = traceback.format_exc()
        show_error_dialog(
            "Application Error",
            f"An unexpected error occurred: {str(e)}",
            error_details
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
