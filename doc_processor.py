
import os
import json
import time
import logging
import pika
from pika.exceptions import AMQPConnectionError
from pathlib import Path
from docling.document_converter import DocumentConverter

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
CONSUME_QUEUE = os.getenv('CONSUME_QUEUE', 'file_events')
PUBLISH_QUEUE = os.getenv('PUBLISH_QUEUE', 'processed_docs')

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

class DocumentProcessor:
    def __init__(self):
        self.converter = DocumentConverter()

    def process_file(self, file_path_str):
        """Processes a file based on its extension."""
        try:
            file_path = Path(file_path_str)
            if not file_path.exists():
                logging.error(f"File not found: {file_path_str}")
                return None

            docs = []
            if file_path.suffix.lower() == '.pdf':
                result = self.converter.convert(file_path_str)
                markdown = result.document.export_to_markdown()
                doc = {
                    "id": file_path.stem,
                    "content": markdown,
                    "type": "pdf",
                    "source": file_path.name,
                    "metadata": {
                        "format": "markdown",
                        "page_count": len(result.document.pages) if hasattr(result.document, 'pages') else 0
                    }
                }
                docs.append(doc)
                logging.info(f"Processed PDF: {file_path.name}")

            elif file_path.suffix.lower() == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure data is a list of documents
                    docs = data if isinstance(data, list) else [data]
                logging.info(f"Processed JSON: {file_path.name}")

            else:
                logging.warning(f"Unsupported file type: {file_path.name}")
                return None

            return docs

        except Exception as e:
            logging.error(f"Failed to process file {file_path_str}: {e}")
            return None

def main():
    processor = DocumentProcessor()
    connection = connect_to_rabbitmq()
    channel = connection.channel()

    # Declare queues
    channel.queue_declare(queue=CONSUME_QUEUE, durable=True)
    channel.queue_declare(queue=PUBLISH_QUEUE, durable=True)

    def callback(ch, method, properties, body):
        try:
            message = json.loads(body)
            file_path = message.get('file_path')
            if file_path:
                logging.info(f"Received message to process file: {file_path}")
                processed_docs = processor.process_file(file_path)

                if processed_docs:
                    # Publish processed documents to the next queue
                    channel.basic_publish(
                        exchange='',
                        routing_key=PUBLISH_QUEUE,
                        body=json.dumps(processed_docs),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # make message persistent
                        ))
                    logging.info(f"Published {len(processed_docs)} processed documents to '{PUBLISH_QUEUE}' queue.")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError:
            logging.error("Failed to decode message body.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logging.error(f"An error occurred in callback: {e}")
            # Decide if you want to requeue or not
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=CONSUME_QUEUE, on_message_callback=callback)

    logging.info(f"Waiting for messages on '{CONSUME_QUEUE}'. To exit press CTRL+C")
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
