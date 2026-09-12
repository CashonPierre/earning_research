import logging, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from pead.panel import build_panel
t0 = time.time(); build_panel(); print(f"done in {time.time()-t0:.0f}s")
