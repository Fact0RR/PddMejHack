import pandas as pd
import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results, Boxes
import matplotlib.pyplot as plt
from typing import List
import supervision
import torch

CLASSES = {0: 'divider-line', 1: 'dotted-line', 2: 'double-line', 3: 'random-line', 4: 'road-sign-line', 5: 'solid-line', 6: 'road-A'}
NAME_TO_CLASS = {v: k for k,v in CLASSES.items()}
BOX_COLORS=np.random.uniform(0, 255, size=(7, 3))


def put_text_on_image(img: np.ndarray, text: str, color: tuple, line: int=0) -> np.ndarray:
	"""
	put_text_on_image Добавить текст детекции нарушений

	Args:
		img (np.ndarray): Изображение
		text (str): Текст
		color (tuple): Цвет
		line (int, optional): Номер строки. Defaults to 0.

	Returns:
		np.ndarray: Аннотированное изображение
	"""
	position = (10, 30+15*line)  # Координаты (x, y)

	# Определяем шрифт, размер, цвет и толщину текста
	font = cv2.FONT_HERSHEY_COMPLEX
	font_scale = 1
	thickness = 2

	# Добавляем текст на изображение
	return cv2.putText(img, text, position, font, font_scale, color, thickness, lineType=cv2.LINE_AA)


def draw_bounding_boxes(result: Results):
    """
    Отрисовывает bounding boxes на изображении.

    :param result: Результат детекции модели YOLO, содержащий bounding boxes, классы и вероятности.
    :param image: Исходное изображение в формате NumPy.
    :return: Изображение с нарисованными bounding boxes в формате NumPy.
    """
    result = result.cpu().numpy()
    # Копируем изображение, чтобы не изменять оригинал
    image_with_boxes = result.orig_img

    # Предполагается, что result содержит списки boxes, scores и class_ids
    boxes = result.boxes.xyxy  # Список координат bounding boxes
    scores = result.boxes.conf  # Список вероятностей
    class_ids = result.boxes.cls.astype(int)  # Список идентификаторов классов

    for box, score, class_id in zip(boxes, scores, class_ids):
        # Получаем координаты bounding box
        x1, y1, x2, y2 = map(int, box)
        

        # Определяем цвет для текущего класса
        color = BOX_COLORS[class_id%len(BOX_COLORS)]

        # Рисуем прямоугольник
        cv2.rectangle(image_with_boxes, (x1, y1), (x2, y2), color, 2)

        # Подписываем bounding box
        class_id = CLASSES[class_id]
        label = f'Class {class_id}: {score:.2f}'
        cv2.putText(image_with_boxes, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return image_with_boxes