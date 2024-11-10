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

from utils import draw_bounding_boxes, put_text_on_image
from line_crossing import solid_line_crossing
from public_trafic import public_trafic_driving

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем переменные окружения с заданием значений по умолчанию
s3 = os.getenv('ENDPOINT', 'http://minio:9000/test-bucket/')  # Значение по умолчанию
ws_url = os.getenv('WEBSOCKET', 'ws://server:8080/ws?type=1')


app = Flask(__name__)

model_path = './models/L-30ep_new_ds.pt'
model = YOLO(model_path)

data = {
	#"xlsx_url": "https://example.com/file.xlsx",
	"crimes": [
		{   
			"video_name":"v1.mp4",
			"name_of_crime": "Превышение скорости",
			"amount_of_fine": 2500,
			"time_of_fine": "300",
			"link":"http://127.0.0.1:9000/test-bucket/AKN00071"
		},
	]
}


def gen_video(urlNameFile, key_websocket, current, all) -> list:
	"""
	gen_video Обработка видео

	Args:
		urlNameFile (_type_): Название видео в S3
		key_websocket (_type_): ключ для вебсокета
		current (_type_): Номер видео (если обрабатывается зип)
		all (_type_): Количество видео

	Return:
		dict: результат обработки
	"""
	url = s3 + urlNameFile
	output_video_path = urlNameFile+'_preccessed_video.mp4'
	skip_frames = 4
	
	# Подключение к WebSocket
	ws = websocket.create_connection(ws_url+'&key='+key_websocket)
	cap = cv2.VideoCapture(url)
	width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
	fps = cap.get(cv2.CAP_PROP_FPS)
	frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

	fourcc = cv2.VideoWriter_fourcc(*'mp4v')
	out_fps = fps # ФПС в выходном файле
	output_video = cv2.VideoWriter(output_video_path, fourcc, out_fps, (width, height))
	#output_video = cv2.VideoWriter(output_video_path, out_fps, (width, height))
	color = {False: (0, 0, 255), True: (0, 255, 0)}

	# штрафы
	solid_cross_fine = 500
	public_trafic_fine = 1500

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
	
	crimes = []
	for i in range(frame_count):
		# пропуск кадров
		if (i)%skip_frames!=0: 
			continue

		ret, frame = cap.read()
		if not ret:
			break

		### обработка кадра
		result = model(frame, verbose=False, conf=0.75)[0]
		box = result.boxes
		# прогон изображениям по различным нарушениям
		solid_line_result = solid_line_crossing(box)
		public_trafic_result = public_trafic_driving(box)
		
		# отрисовка боксов
		#frame = draw_bounding_boxes(result)
		
		# маркеры нарушений
		frame = put_text_on_image(frame, "Сплошная: "+str(solid_line_result), color[solid_line_result])
		frame = put_text_on_image(frame, "Езда по полосе для общ. транспорта: "+str(public_trafic_result), color[public_trafic_result], line=1)

		# запись видео
		output_video.write(frame)
		
		current_time = datetime.datetime.now().time()
		t = f"{current_time.hour}:{current_time.minute}:{current_time.second}"
		percent = ((i+1) / frame_count) * 100
		# Отправляем mess в WebSocket
		if current == 0:
			mess = json.dumps({"Название файла":urlNameFile,"Номер кадра":i+1,"Обработано %":round(percent, 1),"Размер файла":sizeString})
		else:
			mess = json.dumps({"Название файла":urlNameFile,"Номер кадра":i+1,"Обработано %":round(percent, 1),"Размер файла":sizeString,"Сколько видео обработанно":str(current)+"/"+str(all)})
		ws.send(mess)

		# сбор нарушений
		if solid_line_crossing:
			tmp = {   
				"video_name": urlNameFile,
				"name_of_crime": "Пересечение сплошной",
				"amount_of_fine": solid_cross_fine,
				"time_of_fine": str(i//fps),
				"link":f"http://127.0.0.1:9000/test-bucket/{output_video_path}"
			}
			crimes.append(tmp)

		if public_trafic_driving:
			tmp = {   
				"video_name": urlNameFile,
				"name_of_crime": "Проезд по полосе для общ. транспорта",
				"amount_of_fine": public_trafic_fine,
				"time_of_fine": str(i//fps),
				"link":f"http://127.0.0.1:9000/test-bucket/{output_video_path}"
			}
			crimes.append(tmp)

	# Закрываем соединение WebSocket
	ws.close()
	cap.release()
	output_video.release()

	client.fput_object('test-bucket', output_video_path, output_video_path, content_type='video/mp4')
	return crimes


@app.route('/data', methods=['GET'])
def get_data():
	print('video got')
	url_name_file = request.args.get('url')
	key_websocket = request.args.get('key')
	crimes = gen_video(url_name_file,key_websocket,0,0)
	data = {
		"xlsx_url": "",
		"crimes": crimes
	}
	print('video proccessed')
	return jsonify(data) 


@app.route('/datazip',methods=['POST'])
def post_datazip():
	print('zip got')
	key_name_file = request.args.get('key')
	print(key_name_file)
	body = request.get_json()  # или request.data, в зависимости от формата данных
	files = body.get('files', [])
	# Проверяем, были ли получены файлы
	if not files:
		return jsonify({'error': 'No files provided'}), 400
	
	# Например, выводим имена файлов
	i = 0
	total_crimes = []
	for file in files:
		i = i+1
		part_before_slash = file.split('/')[0]
		crimes = gen_video(file, key_name_file, i, len(files))
		total_crimes.extend(crimes)
		print(part_before_slash)  # Здесь можете обрабатывать файлы как вам нужно
	data = {
		"xlsx_url": "",
		"crimes": total_crimes
	}
	print('zip proccessed')
	return jsonify(data), 200

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)