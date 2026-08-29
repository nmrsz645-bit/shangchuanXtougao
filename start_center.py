from pathlib import Path
import runpy


runpy.run_path(Path(__file__).with_name("投稿中心.py"), run_name="__main__")
