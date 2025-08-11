#!/usr/bin/env python3
"""Basic tests for core functionality."""

import sys
from pathlib import Path

def test_imports():
    """Test if core modules can be imported without errors."""
    print("🧪 Testing imports...")
    
    try:
        from core.config import load_config, get_config, set_config
        print("  ✅ core.config")
    except Exception as e:
        print(f"  ❌ core.config: {e}")
        return False
    
    try:
        from core.currency import (
            build_price_map, get_asset_price, calculate_portfolio_value,
            build_eur_price_map, calculate_portfolio_eur_value
        )
        print("  ✅ core.currency")
    except Exception as e:
        print(f"  ❌ core.currency: {e}")
        return False
    
    try:
        from core.json_data_manager import JSONDataManager
        print("  ✅ core.json_data_manager")
    except Exception as e:
        print(f"  ❌ core.json_data_manager: {e}")
        return False
    
    try:
        from api.binance_client import BinanceAPIClient
        print("  ✅ api.binance_client")
    except Exception as e:
        print(f"  ❌ api.binance_client: {e}")
        return False
    
    try:
        from ui.chart_widget import ChartWidget, create_chart_widget
        print("  ✅ ui.chart_widget")
    except Exception as e:
        print(f"  ❌ ui.chart_widget: {e}")
        return False
    
    return True

def test_chart_widget_creation():
    """Test chart widget factory function."""
    print("🧪 Testing chart widget creation...")
    
    try:
        from ui.chart_widget import create_chart_widget
        widget, impl = create_chart_widget('pyqtgraph')
        
        if widget and impl:
            print("  ✅ Chart widget created successfully")
            return True
        else:
            print("  ❌ Chart widget creation returned None")
            return False
    except Exception as e:
        print(f"  ❌ Chart widget creation failed: {e}")
        return False

def test_currency_functions():
    """Test currency conversion functions."""
    print("🧪 Testing currency functions...")
    
    try:
        from core.currency import build_price_map, calculate_portfolio_value
        
        # Mock ticker data
        tickers = {
            'BTCEUR': 45000.0,
            'ETHEUR': 3000.0,
            'ADAEUR': 0.5,
            'USDTEUR': 0.85
        }
        
        # Test price map building
        price_map = build_price_map(tickers, 'EUR')
        
        if 'BTC' in price_map and price_map['BTC'] == 45000.0:
            print("  ✅ Price map building works")
        else:
            print(f"  ❌ Price map building failed: {price_map}")
            return False
        
        # Test portfolio calculation
        balances = {'BTC': 0.1, 'ETH': 1.0, 'ADA': 1000.0}
        portfolio_value = calculate_portfolio_value(balances, price_map, 'EUR')
        
        expected_value = 0.1 * 45000.0 + 1.0 * 3000.0 + 1000.0 * 0.5  # 4500 + 3000 + 500 = 8000
        if abs(portfolio_value - expected_value) < 0.01:
            print(f"  ✅ Portfolio calculation works: {portfolio_value:.2f} EUR")
        else:
            print(f"  ❌ Portfolio calculation failed: {portfolio_value:.2f} != {expected_value:.2f}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Currency function test failed: {e}")
        return False

def test_data_manager():
    """Test JSON data manager."""
    print("🧪 Testing JSON data manager...")
    
    try:
        from core.json_data_manager import JSONDataManager
        import tempfile
        import shutil
        
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            manager = JSONDataManager(temp_dir)
            
            # Test saving and loading purchases
            test_purchases = [
                {
                    'orderId': 'TEST001',
                    'createTime': 1640995200000,  # 2022-01-01
                    'transactionType': '0',
                    'amountFiat': 100.0,
                    'cryptoCurrency': 'BTC',
                    'amountCrypto': 0.002,
                    'price': 50000.0,
                    'fee': 2.0
                }
            ]
            
            saved_count = manager.save_purchases(test_purchases)
            if saved_count == 1:
                print("  ✅ Purchase saving works")
            else:
                print(f"  ❌ Purchase saving failed: {saved_count}")
                return False
            
            loaded_purchases = manager.get_purchases()
            if len(loaded_purchases) == 1 and loaded_purchases[0]['orderId'] == 'TEST001':
                print("  ✅ Purchase loading works")
            else:
                print(f"  ❌ Purchase loading failed: {loaded_purchases}")
                return False
            
            return True
            
        finally:
            # Clean up
            shutil.rmtree(temp_dir)
        
    except Exception as e:
        print(f"  ❌ Data manager test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 Binance Tracker - Core Functionality Tests")
    print("=" * 60)
    
    tests = [
        ("Import Tests", test_imports),
        ("Chart Widget Creation", test_chart_widget_creation),
        ("Currency Functions", test_currency_functions),
        ("Data Manager", test_data_manager),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "0%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Core functionality is working correctly.")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
