#!/usr/bin/env python3
"""
Simple validation script to check test_hunter_api.py structure
"""
import ast
import sys
from pathlib import Path

def validate_script():
    """Validate the test_hunter_api.py script structure"""
    script_path = Path(__file__).parent / "test_hunter_api.py"
    
    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        return False
    
    try:
        # Parse the script to check for syntax errors
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Check syntax
        try:
            ast.parse(code)
            print("✅ Script syntax is valid")
        except SyntaxError as e:
            print(f"❌ Syntax error: {e}")
            return False
        
        # Check for required components
        required_components = [
            "HUNTER_IO_API_KEY",
            "check_account_status",
            "test_domain_search",
            "main",
            "httpx",
            "dotenv"
        ]
        
        missing = []
        for component in required_components:
            if component not in code:
                missing.append(component)
        
        if missing:
            print(f"❌ Missing required components: {', '.join(missing)}")
            return False
        
        print("✅ All required components present")
        print("✅ Script structure is valid")
        print("\n📝 Script is ready to run:")
        print("   python scripts/test_hunter_api.py")
        print("   or")
        print("   make test-hunter")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

if __name__ == "__main__":
    success = validate_script()
    sys.exit(0 if success else 1)

