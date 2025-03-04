@app.route('/deposit/test', methods=['POST'])
def test_deposit():
    """Test endpoint for Tasker deposit confirmation with detailed validation"""
    try:
        data = request.get_json()
        logger.info(f"Test deposit received: {data}")

        validation_results = {
            "format_check": [],
            "data_validation": [],
            "received_data": data
        }

        # Basic format check
        if not data:
            validation_results["format_check"].append("❌ No JSON data received")
            return jsonify(validation_results), 400

        # Check required fields
        required_fields = ['amount', 'phone']
        for field in required_fields:
            if field not in data:
                validation_results["format_check"].append(f"❌ Missing required field: {field}")
            else:
                validation_results["format_check"].append(f"✅ Found required field: {field}")

        # Validate amount format
        try:
            amount = float(data.get('amount', 0))
            if amount <= 0:
                validation_results["data_validation"].append("❌ Amount must be positive")
            else:
                validation_results["data_validation"].append(f"✅ Valid amount: {amount}")
        except (ValueError, TypeError):
            validation_results["data_validation"].append("❌ Invalid amount format - must be a number")

        # Validate phone format
        phone = str(data.get('phone', ''))
        if not phone.isdigit() or len(phone) < 10:
            validation_results["data_validation"].append("❌ Invalid phone number format")
        else:
            validation_results["data_validation"].append(f"✅ Valid phone format: {phone}")

        # Overall validation status
        validation_results["status"] = "valid" if all(
            "❌" not in checks 
            for checks in validation_results["format_check"] + validation_results["data_validation"]
        ) else "invalid"

        return jsonify(validation_results), 200 if validation_results["status"] == "valid" else 400

    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "help": "Make sure to send a POST request with Content-Type: application/json"
        }), 500