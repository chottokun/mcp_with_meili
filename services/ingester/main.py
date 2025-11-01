import os
import time
import json
import pika
import logging
from meilisearch import Client

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# RabbitMQ Connection Details
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
SOURCE_QUEUE = 'processed_documents'

# Meilisearch Connection Details
MEILISEARCH_URL = os.getenv('MEILISEARCH_URL', 'http://meilisearch:7700')
MEILISEARCH_API_KEY = os.getenv('MEILISEARCH_API_KEY')
INDEX_NAME = os.getenv('INDEX_NAME', 'documents')

def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))

def callback(ch, method, properties, body, meili_client):
    try:
        documents = json.loads(body)
        if not documents:
            logging.warning("Received an empty list of documents. Acknowledging message.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logging.info(f"Received {len(documents)} document(s) for indexing.")

        index = meili_client.index(INDEX_NAME)
        task = index.add_documents(documents)

        logging.info(f"Successfully added documents to Meilisearch. Index='{INDEX_NAME}', Task UID={task.task_uid}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode message body: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Discard malformed message
    except Exception as e:
        logging.error(f"An unexpected error occurred during indexing: {e}")
        # Requeue the message for another attempt, as the issue might be transient (e.g., Meilisearch temporary unavailable)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    logging.info("Starting Meilisearch ingester service...")

    # Initialize Meilisearch client
    meili_client = Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
    logging.info(f"Connected to Meilisearch at {MEILISEARCH_URL}")

    # Ensure index exists
    try:
        meili_client.create_index(INDEX_NAME, {'primaryKey': 'id'})
        logging.info(f"Index '{INDEX_NAME}' created.")
    except Exception as e:
        if 'index_already_exists' in str(e):
            logging.info(f"Index '{INDEX_NAME}' already exists.")
        else:
            logging.error(f"Could not create or verify index: {e}")
            # Exit if we can't ensure the index is present
            return

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()

            channel.queue_declare(queue=SOURCE_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)

            on_message_callback = lambda ch, method, properties, body: callback(ch, method, properties, body, meili_client)

            channel.basic_consume(queue=SOURCE_QUEUE, on_message_callback=on_message_callback)

            logging.info("Waiting for processed documents. To exit press CTRL+C")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Could not connect to RabbitMQ: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logging.info("Shutting down Meilisearch ingester.")
            break
        finally:
            if 'connection' in locals() and connection.is_open:
                connection.close()

if __name__ == '__main__':
    main()
