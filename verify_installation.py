#!/usr/bin/env python3
"""Verify that Binance Credit Card Purchase Tracker installation is working correctly."""

import sys
import importlib
from pathlib import Path

def test_python_version():
    """Test Python version compatibility."""
    print("🐍 Testing Python version...")
    
    if sys.version_info >= (3, 8):
        print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} - Compatible")
        return True
    else:
        print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} - Requires 3.8+")
        return False

def test_dependencies():
    """Test if all required dependencies are available."""
    print("\n📦 Testing dependencies...")
    
    dependencies = {
        'httpx': 'HTTP client for API requests',
        'PySide6': 'Qt GUI framework',
        'pydantic': 'Data validation',
        'dotenv': 'Environment file handling',
        'tenacity': 'Retry logic for API calls',
        'dateutil': 'Date parsing utilities',
        'pyqtgraph': 'Chart and graph widgets',
        'numpy': 'Numerical computations for charts'
    }
    
    all_ok = True
    for package, description in dependencies.items():
        try:
            importlib.import_module(package)
            print(f"   ✅ {package:15} - {description}")
        except ImportError:
            print(f"   ❌ {package:15} - {description} (MISSING)")
            all_ok = False
    
    return all_ok

def test_project_structure():
    """Test if project files and directories exist."""
    print("\n📁 Testing project structure...")
    
    project_root = Path(__file__).parent
    required_files = [
        'main.py',
        'requirements.txt',
        'README.md',
        '.env.example',
        '.gitignore',
        'LICENSE'
    ]
    
    required_dirs = [
        'api',
        'core', 
        'ui',
        'data',
        'exports'
    ]
    
    all_ok = True
    
    for file in required_files:
        file_path = project_root / file
        if file_path.exists():
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (MISSING)")
            all_ok = False
    
    for directory in required_dirs:
        dir_path = project_root / directory
        if dir_path.exists() and dir_path.is_dir():
            print(f"   ✅ {directory}/")
        else:
            print(f"   ❌ {directory}/ (MISSING)")
            all_ok = False
    
    return all_ok

def test_imports():
    """Test if application modules can be imported."""
    print("\n🔧 Testing application modules...")
    
    modules_to_test = [
        ('core.config', 'Configuration management'),
        ('core.json_data_manager', 'Data storage'),
        ('core.currency', 'Currency utilities'),
        ('api.binance_client', 'Binance API client'),
        ('api.fiat', 'Fiat orders fetcher'),
        ('ui.main_window', 'Main window'),
        ('ui.settings_dialog', 'Settings dialog'),
        ('ui.chart_widget', 'Chart widget')
    ]
    
    all_ok = True
    
    for module_name, description in modules_to_test:
        try:
            importlib.import_module(module_name)
            print(f"   ✅ {module_name:25} - {description}")
        except ImportError as e:
            print(f"   ❌ {module_name:25} - {description} (IMPORT ERROR: {e})")
            all_ok = False
    
    return all_ok

def test_gui_functionality():
    """Test if GUI components can be initialized."""
    print("\n🖥️  Testing GUI functionality...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        
        # Test if QApplication can be created
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("   ✅ QApplication creation - OK")
        
        # Test basic Qt functionality
        try:
            from ui.chart_widget import ChartWidget
            print("   ✅ Chart widget import - OK")
        except ImportError as e:
            print(f"   ❌ Chart widget import - FAILED: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"   ❌ GUI initialization - FAILED: {e}")
        return False

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("🔍 Binance Credit Card Purchase Tracker - Installation Verification")
    print("=" * 60)
    
    tests = [
        ("Python Version", test_python_version),
        ("Dependencies", test_dependencies),
        ("Project Structure", test_project_structure),
        ("Application Modules", test_imports),
        ("GUI Functionality", test_gui_functionality)
    ]
    
    results = []
    
    for test_name, test_function in tests:
        try:
            result = test_function()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Verification Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} - {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 All tests PASSED! Installation is working correctly.")
        print("\nYou can now run the application with:")
        print("   python main.py")
    else:
        print("❌ Some tests FAILED. Please check the errors above.")
        print("\nTry fixing issues with:")
        print("   python setup.py")
        print("   pip install -r requirements.txt")
    
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
