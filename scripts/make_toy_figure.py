"""Figure 0: the toy example (no data needed)."""
import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def draw(ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 4.8))
    days = [-1, 0, 1, 2, 3, 4, 10, 20, 30, 40]
    close = [90, 100, 100.5, 102, 105, 105.5, 106, 108, 109, 110]
    ax.plot(days, close, "-o", color="black", lw=1.5, ms=4, label="closing price")
    ax.vlines(0, 96, 104, color="black", lw=3, alpha=0.6)
    ax.axhline(104, color="tab:red", ls="--", lw=1, label="earnings-day high = 104")
    ax.annotate("day -1 close 90", (-1, 90), xytext=(0.3, 89.2), fontsize=9, ha="left", arrowprops=dict(arrowstyle="->", color="gray"))
    ax.annotate("earnings day: trades up to 104,\ncloses at 100 (reaction +11%)", (0, 100), xytext=(0.6, 92), fontsize=9, arrowprops=dict(arrowstyle="->", color="gray"))
    ax.plot([1], [100], "o", color="tab:blue", ms=11, zorder=5); ax.annotate("Rule A buys at 100\n(day 1 open)", (1, 100), xytext=(3.5, 96.5), fontsize=9, color="tab:blue", arrowprops=dict(arrowstyle="->", color="tab:blue"))
    ax.plot([3], [105], "s", color="tab:red", ms=8, zorder=5); ax.annotate("day 3: first close above 104", (3, 105), xytext=(6, 103), fontsize=9, color="tab:red", arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.plot([4], [105.5], "o", color="tab:red", ms=11, zorder=5); ax.annotate("Rule B buys at 105\n(day 4 open)", (4, 105.5), xytext=(10, 107.8), fontsize=9, color="tab:red", arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.plot([40], [110], "D", color="tab:green", ms=9, zorder=5); ax.annotate("both sell at 110\n(day 40 close)", (40, 110), xytext=(30, 111.5), fontsize=9, color="tab:green", arrowprops=dict(arrowstyle="->", color="tab:green"))
    ax.fill_between([1, 4], 88, 117, color="tab:blue", alpha=0.08); ax.annotate("run-up: only A holds\n100 -> 105 = +5%", (2.5, 103), xytext=(9, 113.5), ha="left", fontsize=9, color="tab:blue", arrowprops=dict(arrowstyle="->", color="tab:blue"))
    ax.fill_between([4, 40], 88, 117, color="tab:red", alpha=0.05); ax.text(22, 89.5, "both hold: 105 -> 110 = +4.8%", ha="center", fontsize=9, color="tab:red")
    ax.set_xlim(-2, 42); ax.set_ylim(88, 117); ax.set_xlabel("trading days after the earnings day (day 0)"); ax.set_ylabel("price, $")
    ax.set_title("Toy example: A earns +10% = (1 + 5%) x (1 + 4.8%) - 1; B earns +4.8%"); ax.legend(loc="lower right", fontsize=9)
    return ax

if __name__ == "__main__":
    ax = draw(); ax.figure.tight_layout(); ax.figure.savefig("outputs/figures/fig0_toy_example.png", dpi=150); print("outputs/figures/fig0_toy_example.png")
