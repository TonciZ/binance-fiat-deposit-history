#!/usr/bin/env python3
"""Setup script for Binance Credit Card Purchase Tracker."""

import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"   Current version: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print("   Please upgrade Python and try again.")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} is compatible")
    return True

def install_dependencies():
    """Install required dependencies."""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        return False
    
    print("🔧 Installing dependencies...")
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All dependencies installed successfully!")
            return True
        else:
            print(f"❌ Failed to install dependencies:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error during installation: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    project_root = Path(__file__).parent
    directories = ['data', 'exports', 'logs']
    
    for dir_name in directories:
        dir_path = project_root / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"📁 Created directory: {dir_path}")

def setup_environment():
    """Set up environment file if it doesn't exist."""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if not env_file.exists() and env_example.exists():
        try:
            env_file.write_text(env_example.read_text())
            print(f"📄 Created .env file from template")
            print("   Please edit .env with your Binance API credentials")
        except Exception as e:
            print(f"⚠️  Could not create .env file: {e}")

def main():
    """Main setup function."""
    print("=" * 60)
    print("📈 Binance Credit Card Purchase Tracker - Setup")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed due to dependency installation errors.")
        print("You can try installing manually with:")
        print("   pip install -r requirements.txt")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Set up environment
    setup_environment()
    
    print("\n" + "=" * 60)
    print("🎉 Setup completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Edit .env file with your Binance API credentials")
    print("2. Run the application: python main.py")
    print("\nFor help, see README.md")
    
    input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
