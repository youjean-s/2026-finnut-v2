import os
import sys
import inspect

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import utils.parser as p

sample = "카카오페이\n스타벅스\n2025-01-01 12:30\n5,000원"

print("parser file:", p.__file__)
print("function object:", p.parse_push_notification)
src = inspect.getsource(p.parse_push_notification)
print("source first line:", src.splitlines()[0])
print("source last line:", src.splitlines()[-1])

out = p.parse_push_notification(sample)
print("output:", out)