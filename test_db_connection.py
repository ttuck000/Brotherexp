#!/usr/bin/env python3
"""
Database Connection Test Script
This script helps diagnose SQL Server connection issues
"""

import pyodbc
import os
from config import Config

try:
    # 데이터베이스 연결
    conn_str = Config.PYODBC_CONN_STR
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("데이터베이스 연결 성공!")
    
    # 잘못된 데이터 수정
    test_purchase_no = "PO202507210007"
    item_code = "CO-HIPS-GRAY"
    warehouse_code = "A_Scrap"
    
    print(f"\n=== 잘못된 데이터 수정 ===")
    
    # 현재 잘못된 재고 확인
    cursor.execute("""
        SELECT InventoryId, CurrentStock
        FROM dbo.Inventory
        WHERE WarehouseCode = ? AND ItemCode = ?
    """, (warehouse_code, item_code))
    
    current_inventory = cursor.fetchone()
    if current_inventory:
        print(f"현재 잘못된 재고: ID={current_inventory.InventoryId}, 현재고={current_inventory.CurrentStock}")
        
        # 올바른 재고로 수정 (기존 1개 + 매입 10개 = 11개)
        correct_stock = 11.0
        cursor.execute("""
            UPDATE dbo.Inventory
            SET CurrentStock = ?
            WHERE InventoryId = ?
        """, (correct_stock, current_inventory.InventoryId))
        
        print(f"재고 수정: {current_inventory.CurrentStock} -> {correct_stock}")
        
        # 수불내역의 BalanceQty도 수정
        cursor.execute("""
            UPDATE dbo.Inventory_Transaction
            SET BalanceQty = ?
            WHERE RefNo = ? AND ItemCode = ?
        """, (correct_stock, test_purchase_no, item_code))
        
        print(f"수불내역 BalanceQty 수정: {correct_stock}")
        
        conn.commit()
        print("데이터 수정 완료")
    else:
        print("수정할 재고 데이터가 없습니다.")
    
    # 수정 후 확인
    print(f"\n=== 수정 후 데이터 확인 ===")
    cursor.execute("""
        SELECT InventoryId, CurrentStock
        FROM dbo.Inventory
        WHERE WarehouseCode = ? AND ItemCode = ?
    """, (warehouse_code, item_code))
    
    updated_inventory = cursor.fetchone()
    if updated_inventory:
        print(f"수정 후 재고: ID={updated_inventory.InventoryId}, 현재고={updated_inventory.CurrentStock}")
    
    cursor.execute("""
        SELECT TransId, InQty, OutQty, BalanceQty
        FROM dbo.Inventory_Transaction
        WHERE RefNo = ? AND ItemCode = ?
    """, (test_purchase_no, item_code))
    
    updated_transaction = cursor.fetchone()
    if updated_transaction:
        print(f"수정 후 수불내역: ID={updated_transaction.TransId}, 입고={updated_transaction.InQty}, 출고={updated_transaction.OutQty}, 잔고={updated_transaction.BalanceQty}")
    
    conn.close()
    print("\n데이터베이스 연결 종료")
    
except Exception as e:
    print(f"오류 발생: {str(e)}")

def test_connection_string():
    """Test the current connection string from config"""
    print("=== Testing Current Connection String ===")
    
    # Current connection string from config.py
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};" +
        "SERVER=118.67.132.208,1433;" +
        "DATABASE=BRO_EXPENSE;" +
        "UID=brother;" +
        "PWD=jobgate@m1n;" +
        "TrustServerCertificate=yes"
    )
    
    print(f"Connection String: {conn_str}")
    print(f"Server: 118.67.132.208:1433")
    print(f"Database: BIGBOY")
    print(f"Username: brother")
    print(f"Password: jobgate@m1n")
    print()
    
    try:
        print("Attempting to connect...")
        conn = pyodbc.connect(conn_str)
        print("✅ SUCCESS: Database connection established!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        print(f"SQL Server Version: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
        
    except pyodbc.Error as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_alternative_connections():
    """Test alternative connection methods"""
    print("\n=== Testing Alternative Connection Methods ===")
    
    # Test 1: Windows Authentication (if available)
    print("\n1. Testing Windows Authentication...")
    try:
        conn_str_windows = (
            "DRIVER={ODBC Driver 17 for SQL Server};" +
            "SERVER=118.67.132.208,1433;" +
            "DATABASE=BRO_EXPENSE;" +
            "Trusted_Connection=yes;" +
            "TrustServerCertificate=yes"
        )
        conn = pyodbc.connect(conn_str_windows)
        print("✅ SUCCESS: Windows Authentication works!")
        conn.close()
        return True
    except pyodbc.Error as e:
        print(f"❌ Windows Authentication failed: {str(e)}")
    
    # Test 2: Different driver versions
    drivers_to_test = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server", 
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server"
    ]
    
    print("\n2. Testing different ODBC drivers...")
    for driver in drivers_to_test:
        try:
            conn_str = (
                f"DRIVER={{{driver}}};" +
                "SERVER=118.67.132.208,1433;" +
                "DATABASE=BRO_EXPENSE;" +
                "UID=brother;" +
                "PWD=jobgate@m1n;" +
                "TrustServerCertificate=yes"
            )
            conn = pyodbc.connect(conn_str)
            print(f"✅ SUCCESS: {driver} works!")
            conn.close()
            return True
        except pyodbc.Error as e:
            print(f"❌ {driver} failed: {str(e)}")
    
    return False

def list_available_drivers():
    """List all available ODBC drivers"""
    print("\n=== Available ODBC Drivers ===")
    drivers = pyodbc.drivers()
    for i, driver in enumerate(drivers, 1):
        print(f"{i}. {driver}")

def test_network_connectivity():
    """Test basic network connectivity"""
    print("\n=== Testing Network Connectivity ===")
    
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('118.67.132.208', 1433))
        sock.close()
        
        if result == 0:
            print("✅ SUCCESS: Network connection to SQL Server is available")
            return True
        else:
            print("❌ ERROR: Cannot connect to SQL Server on port 1433")
            return False
    except Exception as e:
        print(f"❌ ERROR: Network test failed: {str(e)}")
        return False

def suggest_solutions():
    """Provide suggestions for fixing the connection issue"""
    print("\n=== Suggested Solutions ===")
    print("1. Verify SQL Server credentials:")
    print("   - Check if username 'brother' exists in SQL Server")
    print("   - Verify password 'jobgate@m1n' is correct")
    print("   - Ensure the user has access to BIGBOY database")
    
    print("\n2. Check SQL Server configuration:")
    print("   - Ensure SQL Server is running on 118.67.132.208:1433")
    print("   - Verify SQL Server Authentication Mode allows SQL logins")
    print("   - Check if the user account is not locked or disabled")
    
    print("\n3. Network and firewall:")
    print("   - Ensure port 1433 is open on the server")
    print("   - Check if any firewall is blocking the connection")
    print("   - Verify the server IP address is correct")
    
    print("\n4. Alternative approaches:")
    print("   - Try Windows Authentication if available")
    print("   - Use a different ODBC driver version")
    print("   - Consider using a connection string with additional parameters")

def create_alternative_config():
    """Create alternative configuration options"""
    print("\n=== Alternative Configuration Options ===")
    
    alternatives = [
        {
            "name": "Windows Authentication",
            "conn_str": (
                "DRIVER={ODBC Driver 17 for SQL Server};" +
                "SERVER=118.67.132.208,1433;" +
                "DATABASE=BRO_EXPENSE;" +
                "Trusted_Connection=yes;" +
                "TrustServerCertificate=yes"
            )
        },
        {
            "name": "SQL Authentication with Timeout",
            "conn_str": (
                "DRIVER={ODBC Driver 17 for SQL Server};" +
                "SERVER=118.67.132.208,1433;" +
                "DATABASE=BRO_EXPENSE;" +
                "UID=brother;" +
                "PWD=jobgate@m1n;" +
                "TrustServerCertificate=yes;" +
                "Connection Timeout=30;" +
                "Command Timeout=30"
            )
        },
        {
            "name": "SQL Authentication with Encryption",
            "conn_str": (
                "DRIVER={ODBC Driver 17 for SQL Server};" +
                "SERVER=118.67.132.208,1433;" +
                "DATABASE=BRO_EXPENSE;" +
                "UID=brother;" +
                "PWD=jobgate@m1n;" +
                "TrustServerCertificate=yes;" +
                "Encrypt=yes"
            )
        }
    ]
    
    for alt in alternatives:
        print(f"\n{alt['name']}:")
        print(alt['conn_str'])

if __name__ == "__main__":
    print("Database Connection Diagnostic Tool")
    print("=" * 50)
    print(f"Test run at: {datetime.now()}")
    
    # List available drivers
    list_available_drivers()
    
    # Test network connectivity
    network_ok = test_network_connectivity()
    
    # Test current connection
    current_ok = test_connection_string()
    
    # Test alternative connections
    if not current_ok:
        alternative_ok = test_alternative_connections()
    
    # Provide suggestions
    if not current_ok:
        suggest_solutions()
        create_alternative_config()
    
    print("\n" + "=" * 50)
    if current_ok:
        print("✅ Database connection is working correctly!")
    else:
        print("❌ Database connection failed. Please check the suggestions above.") 