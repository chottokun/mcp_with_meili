
import os
import json
import time
import logging
import pika
from pika.exceptions import AMQPConnectionError
from meilisearch import Client
from meilisearch.errors import MeilisearchApiError

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables from docker-compose
MEILISEARCH_URL = os.getenv('MEILISEARCH_URL', 'http://meilisearch:7700')
MEILISEARCH_API_KEY = os.getenv('MEILISEARCH_API_KEY')
INDEX_NAME = os.getenv('INDEX_NAME', 'documents')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
CONSUME_QUEUE = os.getenv('CONSUME_QUEUE', 'processed_docs')

def connect_to_rabbitmq():
    """Establish a connection to RabbitMQ, with retries."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials)
    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            logging.info("Successfully connected to RabbitMQ.")
            return connection
        except AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def get_meilisearch_client():
    """Get a Meilisearch client instance."""
    return Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)

def main():
    meili_client = get_meilisearch_client()
    connection = connect_to_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue=CONSUME_QUEUE, durable=True)

    # Ensure the Meilisearch index exists
    try:
        meili_client.get_index(INDEX_NAME)
        logging.info(f"Meilisearch index '{INDEX_NAME}' already exists.")
    except MeilisearchApiError:
        logging.info(f"Meilisearch index '{INDEX_NAME}' not found, creating...")
        meili_client.create_index(INDEX_NAME, {'primaryKey': 'id'})
        logging.info(f"Meilisearch index '{INDEX_NAME}' created.")
        # Set searchable attributes to ensure content is searchable
        meili_client.index(INDEX_NAME).update_searchable_attributes(['content', 'source', 'metadata.chunk_index'])
        logging.info(f"Meilisearch index '{INDEX_NAME}' searchable attributes updated.")

    def callback(ch, method, properties, body):
        try:
            documents = json.loads(body)
            if not documents:
                logging.warning("Received an empty list of documents.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            logging.info(f"Received {len(documents)} documents to ingest. First document: {documents[0] if documents else 'N/A'}")

            try:
                task = meili_client.index(INDEX_NAME).add_documents(documents)
                logging.info(f"Successfully sent {len(documents)} documents to Meilisearch. Task UID: {task.task_uid}. Documents sent: {documents}")
                
                # Wait for the task to complete
                meili_client.wait_for_task(task.task_uid)
                logging.info(f"Meilisearch task {task.task_uid} completed.")

            except MeilisearchApiError as e:
                logging.error(f"Failed to ingest documents into Meilisearch: {e}")
                # Depending on the error, you might want to requeue
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError:
            logging.error("Failed to decode message body.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logging.error(f"An unexpected error occurred in callback: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=CONSUME_QUEUE, on_message_callback=callback)

    logging.info(f"Waiting for processed documents on '{CONSUME_QUEUE}'. To exit press CTRL+C")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logging.info("Stopping consumer.")
        channel.stop_consuming()
    finally:
        connection.close()
        logging.info("RabbitMQ connection closed.")


if __name__ == "__main__":
    main()
