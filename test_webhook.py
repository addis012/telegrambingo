import requests
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_webhooks():
    """
    Test script to verify both webhook endpoints:
    1. /webhook/test - Validates data format
    2. /webhook/deposit - Processes actual deposits
    """
    # Base URL - update this with your actual domain
    base_url = "http://0.0.0.0:5000"
    
    # Test data
    test_data = {
        "amount": 100.0,
        "phone": "0911234567"  # Use a registered user's phone number
    }

    # Headers
    headers = {
        "Content-Type": "application/json"
    }

    # 1. Test the validation endpoint
    logger.info("Testing validation endpoint...")
    try:
        response = requests.post(
            f"{base_url}/webhook/test",
            json=test_data,
            headers=headers
        )
        print("\nValidation Test Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        logger.error(f"Validation test failed: {e}")

    # 2. Test the actual deposit endpoint
    logger.info("\nTesting deposit endpoint...")
    try:
        response = requests.post(
            f"{base_url}/webhook/deposit",
            json=test_data,
            headers=headers
        )
        print("\nDeposit Test Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        logger.error(f"Deposit test failed: {e}")

if __name__ == "__main__":
    test_webhooks()
