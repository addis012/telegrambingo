import requests
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_webhooks():
    """
    Test script to test both webhook endpoints:
    1. /webhook/test - For validating data format 
    2. /webhook/deposit - For actual deposit processing
    """
    # Test URLs - try both local and production
    urls = [
        "http://0.0.0.0:5000",  # Local development
        "https://bingoblaster.addisumelke01.repl.co",  # Production
    ]

    # Test data (matching Tasker SMS format)
    test_data = {
        "amount": 100.0,
        "phone": "0911234567"  # Use your actual registered phone number here
    }

    headers = {
        "Content-Type": "application/json"
    }

    for base_url in urls:
        logger.info(f"\nTesting with base URL: {base_url}")

        # 1. Test the validation endpoint
        logger.info("\nTesting webhook validation endpoint...")
        try:
            response = requests.post(
                f"{base_url}/webhook/test",
                json=test_data,
                headers=headers,
                timeout=10
            )
            print("\nValidation Test Response:")
            print(json.dumps(response.json(), indent=2))

            if response.status_code == 200:
                logger.info("✅ Validation test successful!")
            else:
                logger.error(f"❌ Validation test failed with status code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection error for validation test: {e}")
            continue  # Try next URL

        # 2. Test the actual deposit endpoint
        logger.info("\nTesting deposit endpoint...")
        try:
            response = requests.post(
                f"{base_url}/webhook/deposit",
                json=test_data,
                headers=headers,
                timeout=10
            )
            print("\nDeposit Test Response:")
            print(json.dumps(response.json(), indent=2))

            if response.status_code == 200:
                logger.info("✅ Deposit test successful!")
            else:
                logger.error(f"❌ Deposit test failed with status code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection error for deposit test: {e}")
            continue

if __name__ == "__main__":
    test_webhooks()