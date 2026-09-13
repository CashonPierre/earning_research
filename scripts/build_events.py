import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])  # always run from the repo root
import json, logging, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
import pandas as pd
from pead.events import build_events, timing_validation, PARAMS
t0 = time.time()
ev, funnel = build_events()
out = pathlib.Path("outputs/tables"); out.mkdir(parents=True, exist_ok=True)
pd.Series(funnel, name="n_events").rename_axis("step").to_csv(out / "sample_funnel.csv")
print(json.dumps(funnel, indent=1))
tv = timing_validation(ev); tv.to_csv(out / "timing_validation.csv"); print(tv.round(3).to_string())
sel = ev[ev.selected]
print("selected events:", len(sel), "| tickers:", sel.ticker.nunique(), "| quarters:", sel.quarter.nunique(), "| timing:", sel.timing.value_counts().to_dict())
print("AR0 selected: median %.3f, mean %.3f | threshold median %.3f" % (sel.ar0.median(), sel.ar0.mean(), sel.threshold.median()))
print("range_pos terciles (selected):", sel.range_pos.quantile([.1,.25,.5,.75,.9]).round(2).to_dict())
print("events per year (selected):", sel.d0.dt.year.value_counts().sort_index().to_dict())
json.dump(PARAMS, open(out / "event_params.json", "w"), indent=1)
print(f"done in {time.time()-t0:.0f}s")
