import datetime
from io import BytesIO
import json
import time
from flask import Flask, Response, jsonify, request, send_file
import cv2
import numpy as np
import requests
from ultralytics import YOLO
import os
from dotenv import load_dotenv
import websocket
from minio import Minio
from minio.error import S3Error

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем переменные окружения с заданием значений по умолчанию
s3 = os.getenv('ENDPOINT', 'http://minio:9000/test-bucket/')  # Значение по умолчанию
ws_url = os.getenv('WEBSOCKET', 'ws://server:8080/ws?type=1')


app = Flask(__name__)
#model = YOLO('yolov8n.pt')

data = {
    "xlsx_url": "https://example.com/file.xlsx",
    "crimes": [
        {   
            "video_name":"v1.mp4",
            "name_of_crime": "Превышение скорости",
            "amount_of_fine": 2500,
            "time_of_fine": "300",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00071"
        },
        {
            "video_name":"v7.mp4",
            "name_of_crime": "Проезд на красный свет",
            "amount_of_fine": 5000,
            "time_of_fine": "123",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00077"
        },
        {
            "video_name":"v7.mp4",
            "name_of_crime": "Парковка в неположенном месте",
            "amount_of_fine": 3000,
            "time_of_fine": "321",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00077"
        },
        {   
            "video_name":"v3.mp4",
            "name_of_crime": "Непристегнутый ремень безопасности",
            "amount_of_fine": 1500,
            "time_of_fine": "441",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00073"
        },
        {
            "video_name":"v3.mp4",
            "name_of_crime": "Управление без прав",
            "amount_of_fine": 10000,
            "time_of_fine": "234",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00073"
        },
        {
            "video_name":"v5.mp4",
            "name_of_crime": "Вождение в состоянии алкогольного опьянения",
            "amount_of_fine": 25000,
            "time_of_fine": "6522",
            "link":"http://127.0.0.1:9000/test-bucket/AKN00075"
        }
    ]
}

def gen_video(urlNameFile,key_websocket,current,all, dir):
    url = s3 + urlNameFile
    # Подключение к WebSocket
    ws = websocket.create_connection(ws_url+'&key='+key_websocket)
    cap = cv2.VideoCapture(url)
    i = 0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Создание клиента MinIO
    client = Minio(
        os.getenv('S3URL', 'minio:9000/'),
        access_key="minio-user",
        secret_key="minio-password",
        secure=False,  # или True, если вы используете HTTPS
    )
    # Получение размера файла
    sizeString = ""
    try:

        stat = client.stat_object("test-bucket", urlNameFile)

        sizeString = str(round(stat.size/(1024.0 * 1024.0),2))+" МБ"
    except S3Error as e:
        sizeString = "Ошибка при подключении к S3"
        print(e)
    
    while True:
        i += 1

        ret, frame = cap.read()
        if not ret:
            break
        else:
            current_time = datetime.datetime.now().time()
            t = f"{current_time.hour}:{current_time.minute}:{current_time.second}"
            percent = (i / frame_count) * 100
            if current == 0:
                mess = json.dumps({"Название файла":urlNameFile,"Номер кадра":i,"Обработано %":round(percent, 1),"Размер файла":sizeString})
            else:
                mess = json.dumps({"Название файла":urlNameFile,"Номер кадра":i,"Обработано %":round(percent, 1),"Размер файла":sizeString,"Сколько видео обработанно":str(current)+"/"+str(all)})
            ws.send(mess)
            # Отправляем mess в WebSocket
            # Закрываем соединение WebSocket
    ws.close()
    cap.release()

@app.route('/image', methods=['GET'])
def get_image():
    
    url_name_file = request.args.get('url')

    print(s3+url_name_file)
    # Получаем изображение по URL
    response = requests.get(s3+url_name_file)

    # Проверяем статус ответа
    if response.status_code != 200:
        return jsonify({'error': 'Не удалось получить изображение по указанному URL'}), 400

    # Преобразуем содержимое ответа в массив NumPy
    image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
    
    # Декодируем массив в изображение OpenCV
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        return jsonify({'error': 'Не удалось декодировать изображение'}), 400
        
    # Кодируем изображение в формат JPEG и сохраняем в буфер
    _, encoded_image = cv2.imencode('.jpg', image)
    byte_img = BytesIO(encoded_image.tobytes())  # Преобразуем в поток байтов

    return send_file(byte_img, mimetype='image/jpeg')  # Возвращаем изображение в байтах

@app.route('/data', methods=['GET'])
def get_data():
    url_name_file = request.args.get('url')
    key_websocket = request.args.get('key')
    gen_video(url_name_file,key_websocket,0,0,"")
    return jsonify(data) 

@app.route('/datazip',methods=['POST'])
def post_datazip():
    key_name_file = request.args.get('key')
    print(key_name_file)
    body = request.get_json()  # или request.data, в зависимости от формата данных
    files = body.get('files', [])
    # Проверяем, были ли получены файлы
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    
    # Например, выводим имена файлов
    i = 0
    for file in files:
        i = i+1
        part_before_slash = file.split('/')[0]
        gen_video(file,key_name_file,i,len(files),part_before_slash)
        print(part_before_slash)  # Здесь можете обрабатывать файлы как вам нужно

    return jsonify(data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)