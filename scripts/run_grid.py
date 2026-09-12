"""Stage 5: parameter grid W x H on selection (2005-2014) and hold-out (2015-2026)."""
import pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from pead.backtest import Windows, run_rules
from pead.analysis import cell_stats
SEL_END = "2014-12-31"; OUT = pathlib.Path("outputs/tables")
t0 = time.time()
ev = pd.read_parquet("data/processed/events.parquet"); sel = ev[ev.selected].reset_index(drop=True)
win = Windows(sel); selmask = (sel.d0 <= SEL_END).to_numpy()
rows = []
for W in (5, 10, 15, 20):
    for H in (20, 40, 60):
        tmp = run_rules(win, W, H)
        m = int(np.nanmedian(tmp.loc[selmask & tmp.entered_B.to_numpy(), "k_B"]))
        res = run_rules(win, W, H, m_fixed=m); res = res[res.valid_A]
        for per, mask in (("selection_2005_2014", selmask), ("holdout_2015_2026", ~selmask)):
            r = res[mask[res.index]]
            # matched control needs a Windows restricted to the same events; approximate by season matching within full win
            rows.append(cell_stats(win, res.assign(_keep=mask[res.index])[lambda d: d._keep].drop(columns="_keep"), H, per, {"W": W, "H": H, "m_fixed": m}))
        print(f"W={W} H={H} done {time.time()-t0:.0f}s", flush=True)
g = pd.DataFrame(rows); g.to_csv(OUT / "grid_results.csv", index=False)
show = g[["label","W","H","n_events","share_entered_B","CAR_A","CAR_B","B_minus_A","B_minus_A_lo","B_minus_A_hi","PRIMARY_post_minus_matched","PRIMARY_lo","PRIMARY_hi"]]
print(show.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
selg = g[g.label=="selection_2005_2014"].sort_values("PRIMARY_lo", ascending=False)
best = selg.iloc[0]; print(f"\nSelected cell by largest lower CI of PRIMARY in 2005-2014: W={int(best.W)} H={int(best.H)} (PRIMARY {best.PRIMARY_post_minus_matched:.5f} [{best.PRIMARY_lo:.5f}, {best.PRIMARY_hi:.5f}])")
hb = g[(g.label=="holdout_2015_2026") & (g.W==best.W) & (g.H==best.H)].iloc[0]
print(f"Hold-out for that cell: PRIMARY {hb.PRIMARY_post_minus_matched:.5f} [{hb.PRIMARY_lo:.5f}, {hb.PRIMARY_hi:.5f}], B-A {hb.B_minus_A:.4f} [{hb.B_minus_A_lo:.4f}, {hb.B_minus_A_hi:.4f}]")
pd.Series({"W": int(best.W), "H": int(best.H)}).to_json(OUT / "grid_selected_cell.json")
