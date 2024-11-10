import pandas as pd
import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results, Boxes
import matplotlib.pyplot as plt
from typing import List
import supervision
import torch

from utils import CLASSES, NAME_TO_CLASS

def public_trafic_driving(frame: Boxes) -> bool:
	"""
	solid_line_crossing Проверка переезда сплошной

	Args:
		frame (Results): размеченный кадр
	"""
	public_trafic_line = (NAME_TO_CLASS['road-A'], NAME_TO_CLASS['road-sign-line'])
	# выход, если в кадре нет сплошных
	if not (public_trafic_line[0] in frame.cls or public_trafic_line[1] in frame.cls):
		return False
	
	# проход по всем боксам
	for box in frame:
		if not box.cls[0] == public_trafic_line:
			continue
		box_coords = box.xyxyn[0]
		box_center_x = (box_coords[2] + box_coords[0])/2
		box_center_y = (box_coords[3] + box_coords[1])/2
		if box_center_y>=0.66:
			continue
		# если полоса почти перпендикулярна машине
		if box_coords[0]<0.5 and box_coords[2]>0.5:
			return True
	return False