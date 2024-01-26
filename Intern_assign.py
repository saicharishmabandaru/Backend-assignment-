from flask import Flask, request, jsonify
from celery import Celery
from requests import request as make_request
import time

app = Flask(__name__)

# Configuration for Celery
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


@celery.task(bind=True, max_retries=5)
def execute_webhook(self, webhook_url, headers):
    try:
        # Make HTTP request to the provided webhook_url with headers
        response = make_request(method='POST', url=webhook_url, headers=headers)

        # Check the response status code
        response.raise_for_status()

        # If successful, return response or perform necessary actions
        return f"Webhook executed successfully. Response: {response.text}"
    except Exception as e:
        # Log the exception and retry with exponential backoff using Celery
        self.retry(countdown=2 ** self.request.retries, exc=e)


# Dummy data store for webhook subscriptions
webhooks = {}
webhook_id_counter = 1


@app.route('/webhooks/', methods=['POST'])
def create_webhook():
    data = request.json
    company_id = data.get('company_id')
    url = data.get('url')
    headers = data.get('headers', {})
    events = data.get('events', [])
    is_active = data.get('is_active', True)
    created_at = int(time.time())
    updated_at = created_at

    webhook = {
        'company_id': company_id,
        'url': url,
        'headers': headers,
        'events': events,
        'is_active': is_active,
        'created_at': created_at,
        'updated_at': updated_at,
    }

    # Save webhook details
    global webhook_id_counter
    webhook_id = webhook_id_counter
    webhook_id_counter += 1
    webhooks[webhook_id] = webhook

    return jsonify({'message': 'Webhook created successfully', 'webhook_id': webhook_id})


@app.route('/webhooks/<int:webhook_id>/', methods=['PATCH'])
def update_webhook(webhook_id):
    data = request.json

    # Check if webhook exists
    if webhook_id in webhooks:
        webhook = webhooks[webhook_id]

        # Update webhook details
        webhook['url'] = data.get('url', webhook['url'])
        webhook['headers'] = data.get('headers', webhook['headers'])
        webhook['events'] = data.get('events', webhook['events'])
        webhook['is_active'] = data.get('is_active', webhook['is_active'])
        webhook['updated_at'] = int(time.time())

        return jsonify({'message': 'Webhook updated successfully'})
    else:
        return jsonify({'error': 'Webhook not found'}), 404


@app.route('/webhooks/<int:webhook_id>/', methods=['DELETE'])
def delete_webhook(webhook_id):
    # Check if webhook exists
    if webhook_id in webhooks:
        del webhooks[webhook_id]
        return jsonify({'message': 'Webhook deleted successfully'})
    else:
        return jsonify({'error': 'Webhook not found'}), 404


@app.route('/webhooks/', methods=['GET'])
def list_webhooks():
    return jsonify({'webhooks': list(webhooks.values())})


@app.route('/webhooks/<int:webhook_id>/', methods=['GET'])
def get_webhook(webhook_id):
    # Check if webhook exists
    if webhook_id in webhooks:
        return jsonify({'webhook': webhooks[webhook_id]})
    else:
        return jsonify({'error': 'Webhook not found'}), 404


if __name__ == '__main__':
    app.run(debug=True)
