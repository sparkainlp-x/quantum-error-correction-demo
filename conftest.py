"""pytest configuration — adds src/ to sys.path so tests can import oes32.*"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
