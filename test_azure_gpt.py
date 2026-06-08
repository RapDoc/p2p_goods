"""
Standalone test module for Azure GPT LLM validation.

This module tests the Azure OpenAI GPT-4 configuration and makes a sample call
to verify the LLM integration is working correctly.

Usage:
    python test_azure_gpt.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_azure_configuration():
    """Verify all required Azure OpenAI environment variables are set."""
    print("\n" + "="*60)
    print("AZURE OPENAI CONFIGURATION CHECK")
    print("="*60)
    
    required_vars = {
        "OPENAI_API_TYPE": "Type of OpenAI API (should be 'azure')",
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI endpoint URL",
        "AZURE_OPENAI_API_KEY": "API key for Azure OpenAI",
        "OPENAI_API_VERSION": "API version (e.g., 2024-05-01-preview)",
        "AZURE_OPENAI_DEPLOYMENT": "Deployment name (e.g., gpt-4)"
    }
    
    config = {}
    all_present = True
    
    for var_name, description in required_vars.items():
        value = os.getenv(var_name, "")
        is_present = bool(value)
        all_present = all_present and is_present
        
        status = "[OK]" if is_present else "[MISSING]"
        print(f"{status} {var_name:30} : {description}")
        if is_present:
            # Mask sensitive values
            if "KEY" in var_name:
                config[var_name] = f"***{value[-4:]}"
            elif "ENDPOINT" in var_name:
                config[var_name] = value[:50] + "..." if len(value) > 50 else value
            else:
                config[var_name] = value
    
    print()
    return all_present, config


def test_openai_import():
    """Test if the openai package is installed."""
    print("="*60)
    print("OPENAI PACKAGE CHECK")
    print("="*60)
    
    try:
        import openai
        print(f"[OK] openai package installed (version: {openai.__version__ if hasattr(openai, '__version__') else 'unknown'})")
        return True
    except ImportError as e:
        print(f"[ERROR] openai package not installed: {e}")
        print("       Install with: pip install openai")
        return False


def test_azure_gpt_call():
    """Make a test call to Azure OpenAI GPT-4."""
    print("\n" + "="*60)
    print("AZURE GPT-4 CONNECTION TEST")
    print("="*60)
    
    try:
        from openai_utils import query_openai
        
        print("\nTest 1: Simple classification prompt")
        print("-" * 60)
        
        test_prompt = (
            "Classify the following text as either: PO, Invoice, or Delivery Challan.\n"
            "Respond with only the document type.\n\n"
            "Text: 'Purchase Order PO-2024-001. Date: 2024-06-08. "
            "Supplier: ABC Corp. Items: 10 units @ $100 each.'"
        )
        
        print(f"Prompt: {test_prompt}\n")
        print("Calling GPT-4...")
        
        response = query_openai(test_prompt, max_tokens=32, temperature=0.1)
        
        if response:
            print(f"[OK] Response received: {response}")
            return True
        else:
            print("[ERROR] Empty response from GPT-4")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Failed to import openai_utils: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] GPT-4 call failed: {type(e).__name__}: {str(e)}")
        return False


def test_azure_gpt_json():
    """Test JSON response parsing from Azure GPT-4."""
    print("\n" + "="*60)
    print("AZURE GPT-4 JSON RESPONSE TEST")
    print("="*60)
    
    try:
        from openai_utils import query_openai_json
        
        print("\nTest 2: JSON response parsing")
        print("-" * 60)
        
        test_prompt = (
            'Extract document information from this text and return as JSON:\n'
            '{"invoice_number": "<value>", "date": "<value>", "vendor": "<value>"}\n\n'
            'Text: "Invoice INV-2024-001. Date: 2024-06-08. Vendor: Acme Inc."'
        )
        
        print(f"Prompt: {test_prompt}\n")
        print("Calling GPT-4 with JSON parsing...")
        
        response = query_openai_json(test_prompt, max_tokens=64)
        
        if response:
            print(f"[OK] JSON response received:")
            import json
            print(json.dumps(response, indent=2))
            return True
        else:
            print("[ERROR] Empty JSON response from GPT-4")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Failed to import openai_utils: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] GPT-4 JSON call failed: {type(e).__name__}: {str(e)}")
        return False


def test_azure_gpt_performance():
    """Test performance of Azure GPT-4 calls."""
    print("\n" + "="*60)
    print("AZURE GPT-4 PERFORMANCE TEST")
    print("="*60)
    
    try:
        from openai_utils import query_openai
        import time
        
        print("\nTest 3: Performance benchmark (5 sequential calls)")
        print("-" * 60)
        
        prompts = [
            "Classify as PO, Invoice, or Delivery Challan: 'Purchase Order PO-001'",
            "Classify as PO, Invoice, or Delivery Challan: 'Invoice INV-001'",
            "Classify as PO, Invoice, or Delivery Challan: 'Delivery Challan DC-001'",
            "Classify as PO, Invoice, or Delivery Challan: 'Unknown Document'",
            "Classify as PO, Invoice, or Delivery Challan: 'Tax Invoice GST-INV-001'"
        ]
        
        times = []
        for i, prompt in enumerate(prompts, 1):
            start = time.time()
            response = query_openai(prompt, max_tokens=16, temperature=0.0)
            elapsed = time.time() - start
            times.append(elapsed)
            
            status = "[OK]" if response else "[ERROR]"
            print(f"  Call {i}: {elapsed:.2f}s {status}")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"\nAverage response time: {avg_time:.2f}s")
            print(f"Fastest call: {min(times):.2f}s")
            print(f"Slowest call: {max(times):.2f}s")
            return True
        else:
            print("[ERROR] No successful calls")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Failed to import openai_utils: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Performance test failed: {type(e).__name__}: {str(e)}")
        return False


def main():
    """Run all Azure GPT validation tests."""
    print("\n" + "="*60)
    print("AZURE GPT-4 VALIDATION TEST SUITE")
    print("="*60)
    
    # Test 1: Configuration
    config_ok, config = check_azure_configuration()
    
    # Test 2: Package import
    import_ok = test_openai_import()
    
    if not config_ok:
        print("\n" + "!"*60)
        print("ERROR: Missing Azure OpenAI configuration!")
        print("!"*60)
        print("\nPlease set the following environment variables:")
        print("  - OPENAI_API_TYPE=azure")
        print("  - AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/")
        print("  - AZURE_OPENAI_API_KEY=your-api-key")
        print("  - OPENAI_API_VERSION=2024-05-01-preview")
        print("  - AZURE_OPENAI_DEPLOYMENT=gpt-4")
        return 1
    
    if not import_ok:
        print("\n" + "!"*60)
        print("ERROR: openai package not installed!")
        print("!"*60)
        return 1
    
    # Test 3: Simple call
    call_ok = test_azure_gpt_call()
    
    # Test 4: JSON call (only if simple call worked)
    json_ok = True
    if call_ok:
        json_ok = test_azure_gpt_json()
    
    # Test 5: Performance (only if previous tests passed)
    perf_ok = True
    if call_ok and json_ok:
        perf_ok = test_azure_gpt_performance()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Configuration Check     : {'PASS' if config_ok else 'FAIL'}")
    print(f"Package Import         : {'PASS' if import_ok else 'FAIL'}")
    print(f"GPT-4 Call Test        : {'PASS' if call_ok else 'FAIL'}")
    print(f"JSON Response Test     : {'PASS' if json_ok else 'FAIL'}")
    print(f"Performance Test       : {'PASS' if perf_ok else 'FAIL'}")
    
    all_passed = config_ok and import_ok and call_ok and json_ok and perf_ok
    
    print("="*60)
    if all_passed:
        print("RESULT: ALL TESTS PASSED")
        print("Azure GPT-4 is configured correctly and operational!")
        return 0
    else:
        print("RESULT: SOME TESTS FAILED")
        print("Please review the errors above and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
