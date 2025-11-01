
import os
import time
import logging
import json
import pika
from pika.exceptions import AMQPConnectionError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
QUEUE_NAME = os.getenv('RABBITMQ_QUEUE', 'file_events')
WATCH_DIRECTORY = os.getenv('WATCH_DIRECTORY', '/input')

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

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, channel, queue_name):
        self.channel = channel
        self.queue_name = queue_name

    def on_created(self, event):
        if not event.is_directory:
            self.publish_message(event.src_path)

    def publish_message(self, file_path):
        """Publish a message to the RabbitMQ queue."""
        try:
            message = json.dumps({'file_path': file_path})
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))
            logging.info(f"Sent message for new file: {file_path}")
        except Exception as e:
            logging.error(f"Failed to send message for {file_path}: {e}")

def main():
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    event_handler = FileChangeHandler(channel, QUEUE_NAME)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=True)
    observer.start()

    logging.info(f"Watching directory: {WATCH_DIRECTORY}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Observer stopped.")
    finally:
        observer.join()
        connection.close()
        logging.info("RabbitMQ connection closed.")

if __name__ == "__main__":
    main()
