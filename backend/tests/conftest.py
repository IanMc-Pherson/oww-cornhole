import sys
import pathlib

# Add the backend directory to sys.path so `app` can be imported
backend_dir = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
