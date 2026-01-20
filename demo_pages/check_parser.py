import os
import sys

# 프로젝트 루트(= demo_pages의 상위 폴더)를 파이썬 경로에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import utils.parser as p
from utils.parser import parse_push_notification

sample = "카카오페이\n스타벅스\n2025-01-01 12:30\n5,000원"

print("parser file:", p.__file__)
print(parse_push_notification(sample))
