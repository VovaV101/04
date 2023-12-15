from flask import Flask, render_template, request, redirect, url_for
import socket
import json
from datetime import datetime
from multiprocessing import Process, Queue


app = Flask(__name__, template_folder='templates', static_folder='static')
last_message_id = 0
socket_queue = Queue()

# Функція для збереження повідомлення в файл
def save_message(username, message):
    global last_message_id
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    message_id = last_message_id + 1
    last_message_id = message_id

    data = {
        "timestamp": timestamp,
        "username": username,
        "message": message
    }

    # Завантажуємо весь вміст файлу у список або створюємо новий список, якщо файл порожній
    try:
        with open('storage/data.json', 'r') as f:
            data_list = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data_list = []

    # Додаємо новий словник до списку
    data_list.append(data)

    # Записуємо весь список у файл як байт-рядок JSON
    with open('storage/data.json', 'w') as f:
        json.dump(data_list, f, indent=2)

# HTTP Server
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/message', methods=['GET', 'POST'])
def message():
    if request.method == 'POST':
        username = request.form['username']
        message_text = request.form['message']

        if username and message_text:
            save_message(username, message_text)

            # Додаємо дані до черги для Socket сервера
            socket_queue.put({'username': username, 'message': message_text})

            return redirect(url_for('index'))

    return render_template('message.html')

# Обробник помилок 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404

# Socket Server
def socket_server(queue):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 5000))
        while True:
            data, addr = s.recvfrom(1024)
            queue.put(data)

def handle_socket_data(data):
    # Отримуємо словник із вхідних даних
    decoded_data = data

    # Завантажуємо весь вміст файлу у список або створюємо новий список, якщо файл порожній
    try:
        with open('storage/data.json', 'r') as f:
            data_list = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data_list = []

    # Перевіряємо, чи аналогічний запис вже існує в списку за умовою username і message
    existing_entry = next((entry for entry in data_list if entry.get("username") == decoded_data.get("username")
                           and entry.get("message") == decoded_data.get("message")), None)

    # Якщо аналогічний запис вже існує, не додаємо його
    if existing_entry is None:
        # Додаємо новий словник до списку
        data_list.append(decoded_data)

        # Записуємо весь список у файл як байт-рядок JSON
        with open('storage/data.json', 'w') as f:
            json.dump(data_list, f, indent=2)

# Запускаємо сервери
if __name__ == "__main__":
    # Запускаємо HTTP сервер у власному процесі
    http_process = Process(target=app.run, kwargs={'debug': False, 'port': 3000})
    http_process.start()

    # Запускаємо Socket сервер у власному процесі
    socket_process = Process(target=socket_server, args=(socket_queue,))
    socket_process.start()

    # Безперервна обробка даних з черги
    while True:
        if not socket_queue.empty():
            data = socket_queue.get()
            try:
                handle_socket_data(data)
            except Exception as e:
                print(f"Error handling socket data: {e}")
