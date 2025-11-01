import os
import time
import json
import pika
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter

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
SOURCE_QUEUE = 'file_events'
DEST_QUEUE = 'processed_documents'

def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))

class DocumentProcessor:
    def __init__(self):
        self.converter = DocumentConverter()

    def process_pdf(self, file_path):
        try:
            logging.info(f"Processing PDF file: {file_path}")
            result = self.converter.convert(str(file_path))
            markdown = result.document.export_to_markdown()
            return {
                "id": Path(file_path).stem,
                "content": markdown,
                "type": "pdf",
                "source": Path(file_path).name,
                "metadata": {
                    "format": "markdown",
                    "page_count": len(result.document.pages) if hasattr(result.document, 'pages') else 0
                }
            }
        except Exception as e:
            logging.error(f"Failed to process PDF {file_path}: {e}")
            return None

    def process_json(self, file_path):
        try:
            logging.info(f"Processing JSON file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Assuming JSON contains a list of documents or a single document
            return data
        except Exception as e:
            logging.error(f"Failed to process JSON {file_path}: {e}")
            return None

def callback(ch, method, properties, body, doc_processor, dest_channel):
    try:
        message = json.loads(body)
        logging.info(f"Received message: {message}")

        filepath = message.get('filepath')
        filetype = message.get('filetype')

        processed_data = None
        if filetype == 'pdf':
            processed_data = doc_processor.process_pdf(filepath)
        elif filetype == 'json':
            processed_data = doc_processor.process_json(filepath)
        else:
            logging.warning(f"Unsupported file type: {filetype}")

        if processed_data:
            # If JSON was a single doc, wrap in a list
            docs_to_publish = processed_data if isinstance(processed_data, list) else [processed_data]

            dest_channel.basic_publish(
                exchange='',
                routing_key=DEST_QUEUE,
                body=json.dumps(docs_to_publish),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logging.info(f"Published {len(docs_to_publish)} processed document(s) to '{DEST_QUEUE}'")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logging.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    logging.info("Starting document processor service...")
    doc_processor = DocumentProcessor()

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()

            # Declare queues
            channel.queue_declare(queue=SOURCE_QUEUE, durable=True)
            channel.queue_declare(queue=DEST_QUEUE, durable=True)

            channel.basic_qos(prefetch_count=1)

            # Create a dedicated channel for publishing to avoid channel closure issues
            publish_channel = connection.channel()

            on_message_callback = lambda ch, method, properties, body: callback(ch, method, properties, body, doc_processor, publish_channel)

            channel.basic_consume(queue=SOURCE_QUEUE, on_message_callback=on_message_callback)

            logging.info("Waiting for messages. To exit press CTRL+C")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Could not connect to RabbitMQ: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logging.info("Shutting down document processor.")
            break
        finally:
            if 'connection' in locals() and connection.is_open:
                connection.close()

if __name__ == '__main__':
    main()
