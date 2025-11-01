import os
import time
import json
import pika
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
WATCH_QUEUE = 'file_events'

def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))

def publish_message(channel, queue_name, message_body):
    try:
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message_body),
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        logging.info(f"Sent message to queue '{queue_name}': {message_body}")
    except Exception as e:
        logging.error(f"Failed to publish message: {e}")

class FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, channel):
        self.channel = channel
        self.supported_formats = {'.pdf', '.json', '.md', '.txt', '.docx'}

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() in self.supported_formats:
            time.sleep(1)  # Wait for file to be fully written
            logging.info(f"Detected new file: {file_path}")

            message = {
                'filepath': str(file_path),
                'filetype': file_path.suffix.lower().lstrip('.')
            }
            publish_message(self.channel, WATCH_QUEUE, message)

def main():
    watch_dir = os.getenv('WATCH_DIR', '/input')
    logging.info(f"Starting file watcher for directory: {watch_dir}")

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            channel.queue_declare(queue=WATCH_QUEUE, durable=True)
            logging.info("Successfully connected to RabbitMQ.")
            break
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Could not connect to RabbitMQ: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    event_handler = FileWatcherHandler(channel)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Shutting down file watcher.")
    finally:
        observer.join()
        connection.close()

if __name__ == '__main__':
    main()
