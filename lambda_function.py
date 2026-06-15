import json
import boto3
import os
import uuid
import re
from datetime import datetime, timezone, date

# Initialize AWS clients outside the handler for connection reuse
secrets_client = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# CORS headers required for all responses
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS'
}


def _response(status_code, body_dict=None):
    """Helper to build HTTP responses including required CORS headers."""
    body = json.dumps(body_dict) if body_dict is not None else ""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': body
    }


def lambda_handler(event, context):
    """Main Lambda handler for MediBook appointment bookings.

    Steps implemented exactly as specified by the function purpose.
    """
    try:
        # STEP 1 - Handle OPTIONS preflight request
        if event.get('httpMethod') == 'OPTIONS':
            return _response(200, {})

        # STEP 2 - Parse request body
        try:
            body = json.loads(event.get('body', '{}') or '{}')
        except Exception:
            print('Invalid JSON body received')
            return _response(400, {'message': 'Invalid JSON body'})

        # STEP 3 - Extract and sanitize all fields (strip whitespace)
        patient_name = (body.get('patient_name') or '').strip()
        email = (body.get('email') or '').strip()
        phone = (body.get('phone') or '').strip()
        appointment_date = (body.get('appointment_date') or '').strip()
        appointment_time = (body.get('appointment_time') or '').strip()
        doctor = (body.get('doctor') or '').strip()
        reason = (body.get('reason') or '').strip()

        # STEP 4 - Validate all required fields exist and are not empty
        required_fields = {
            'patient_name': patient_name,
            'email': email,
            'phone': phone,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'doctor': doctor,
            'reason': reason
        }
        for field_name, value in required_fields.items():
            if not value:
                return _response(400, {'message': f'Missing required field: {field_name}'})

        # STEP 5 - Validate email format using regex
        email_pattern = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
        if not email_pattern.match(email):
            return _response(400, {'message': 'Invalid email format'})

        # STEP 6 - Validate phone is numeric only, 7-15 digits
        if not re.match(r'^\d{7,15}$', phone):
            return _response(400, {'message': 'Invalid phone number format'})

        # STEP 7 - Validate appointment_date is not in the past
        try:
            appt_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except Exception:
            return _response(400, {'message': 'Invalid appointment_date format, expected YYYY-MM-DD'})

        if appt_date_obj < date.today():
            return _response(400, {'message': 'Appointment date cannot be in the past'})

        # STEP 8 - Generate appointment ID
        appointment_id = 'APT-' + str(uuid.uuid4()).replace('-', '').upper()[:8]

        # STEP 9 - Get current UTC timestamp
        created_at = datetime.now(timezone.utc).isoformat()

        # STEP 10 - Retrieve secret from Secrets Manager
        secret_name = os.environ.get('SECRET_NAME')
        if not secret_name:
            print('SECRET_NAME environment variable not set')
            return _response(500, {'message': 'Internal server error'})

        try:
            secret_resp = secrets_client.get_secret_value(SecretId=secret_name)
            secret_string = secret_resp.get('SecretString')
            if not secret_string:
                print('Secrets Manager returned empty secret string')
                return _response(500, {'message': 'Internal server error'})
            secret = json.loads(secret_string)
            table_name = secret.get('tableName')
            sns_topic_arn = secret.get('snsTopicArn')
            if not table_name or not sns_topic_arn:
                print('Secret missing required keys')
                return _response(500, {'message': 'Internal server error'})
        except Exception as e:
            print('Error retrieving secret:', str(e))
            return _response(500, {'message': 'Internal server error'})

        # STEP 11 - Write appointment to DynamoDB
        try:
            appt_table = dynamodb.Table(table_name)
            appt_item = {
                'appointment_id': appointment_id,
                'appointment_date': appointment_date,
                'patient_name': patient_name,
                'email': email,
                'phone': phone,
                'appointment_time': appointment_time,
                'doctor': doctor,
                'reason': reason,
                'status': 'CONFIRMED',
                'created_at': created_at
            }
            appt_table.put_item(Item=appt_item)
        except Exception as e:
            print('Error writing appointment to DynamoDB:', str(e))
            return _response(500, {'message': 'Internal server error'})

        # STEP 12 - Write to audit log table (non-blocking)
        try:
            audit_table_name = os.environ.get('AUDIT_TABLE')
            if audit_table_name:
                audit_table = dynamodb.Table(audit_table_name)
                audit_item = {
                    'log_id': str(uuid.uuid4()),
                    'action': 'APPOINTMENT_CREATED',
                    'appointment_id': appointment_id,
                    'patient_email': email,
                    'doctor': doctor,
                    'appointment_date': appointment_date,
                    'timestamp': created_at
                }
                audit_table.put_item(Item=audit_item)
            else:
                print('AUDIT_TABLE not set; skipping audit log')
        except Exception as e:
            print('Error writing to audit table:', str(e))

        # STEP 13 - Publish SNS confirmation (non-blocking)
        try:
            message = (
                f"Your appointment has been confirmed.\n\n"
                f"Appointment ID: {appointment_id}\n"
                f"Patient Name: {patient_name}\n"
                f"Date: {appointment_date}\n"
                f"Time: {appointment_time}\n"
                f"Doctor: {doctor}\n"
                f"Reason: {reason}\n\n"
                "Please arrive 10 minutes before your appointment.\n"
                "MediBook - Secure Patient Appointment System"
            )
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='MediBook - Appointment Confirmed',
                Message=message
            )
        except Exception as e:
            print('Error publishing SNS confirmation:', str(e))

        # STEP 14 - Return success response
        response_body = {
            'appointment_id': appointment_id,
            'status': 'CONFIRMED',
            'message': 'Appointment booked successfully',
            'patient_name': patient_name,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'doctor': doctor
        }
        return _response(200, response_body)

    except Exception as e:
        # Catch-all server error — log but do not expose details
        print('Unhandled exception in lambda_handler:', str(e))
        return _response(500, {'message': 'Internal server error'})
