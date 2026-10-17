"""Fit vj01's learned value function: logistic regression from agent.py's features to "this player wins".

Reads one or more .npz files from gen_data.py, holds out every 5th game (by seed) for validation so
positions from one game never sit on both sides, standardises the features, fits a few strengths of
L2 regularisation and keeps the one with the best validation log-loss. Writes weights.npz next to
agent.py, with the scaling folded in so play time is one dot product:

    logit = x . w + b

Run from the kit folder, for example:

    .venv\\Scripts\\python ..\\Seed-404\\vj\\vj01_learned_value\\train.py ..\\vj_data\\run1.npz
"""
import os
import sys

sys.path.insert(0, os.getcwd())

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    import argparse
    import time

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, log_loss

    p = argparse.ArgumentParser()
    p.add_argument("data", nargs="+")
    p.add_argument("--C", type=float, nargs="+", default=[0.001, 0.01, 0.1, 1.0])
    p.add_argument("--out", default=os.path.join(HERE, "weights.npz"))
    p.add_argument("--drop", nargs="*", default=[],
                   help="drop every feature whose name contains one of these substrings")
    a = p.parse_args()

    Xs, ys, gs, names = [], [], [], None
    for path in a.data:
        d = np.load(path)
        if names is None:
            names = d["names"]
        assert list(d["names"]) == list(names), f"{path}: different feature set"
        Xs.append(d["X"])
        ys.append(d["y"])
        gs.append(d["game"])
    X = np.concatenate(Xs).astype(np.float64)
    y = np.concatenate(ys)
    g = np.concatenate(gs)
    keep = np.array([not any(s in n for s in a.drop) for n in names])
    if a.drop:
        print("dropped:", [str(n) for n in names[~keep]])
    X, names = X[:, keep], names[keep]
    val = (g % 5) == 0
    print(f"{len(y)} positions from {len(np.unique(g))} games; "
          f"train {(~val).sum()}, validation {val.sum()}")

    mean = X[~val].mean(axis=0)
    scale = X[~val].std(axis=0)
    scale[scale == 0] = 1.0
    Z = (X - mean) / scale

    base_ll = log_loss(y[val], np.full(val.sum(), y[~val].mean()))
    print(f"constant-guess validation log-loss {base_ll:.4f}")
    best = None
    for C in a.C:
        t = time.time()
        m = LogisticRegression(C=C, max_iter=1000)
        m.fit(Z[~val], y[~val])
        pv = m.predict_proba(Z[val])[:, 1]
        ll, acc = log_loss(y[val], pv), accuracy_score(y[val], pv > 0.5)
        print(f"C={C:<6} validation log-loss {ll:.4f}  accuracy {acc:.3f}  ({time.time() - t:.0f} s)")
        if best is None or ll < best[0]:
            best = (ll, acc, C, m)

    ll, acc, C, m = best
    assert len(names) == X.shape[1], (len(names), X.shape[1])
    w = m.coef_[0] / scale
    b = float(m.intercept_[0] - np.sum(m.coef_[0] * mean / scale))
    np.savez(a.out, names=names, w=w, b=np.array(b), C=np.array(C),
             val_logloss=np.array(ll), val_acc=np.array(acc), n_positions=np.array(len(y)))
    top = np.argsort(-np.abs(m.coef_[0]))[:15]
    print(f"kept C={C}: validation log-loss {ll:.4f}, accuracy {acc:.3f} -> {a.out}")
    print("largest standardised weights:")
    for i in top:
        print(f"  {m.coef_[0][i]:+.3f}  {names[i]}")


if __name__ == "__main__":
    main()
