"""Live smoke test of gather + rephrase on 4B, with stub search/open over saved fixture pages.

    python -m sufficiency.eval.live_gather
"""
from __future__ import annotations

import json
from pathlib import Path

from sufficiency import gather, rephrase
from sufficiency.eval.run_check import TODAY, load

orig, new = load()
F = {f["id"]: f for f in orig + new}
PAGES = {f["url"]: {"title": f["page"].splitlines()[0], "text": f["page"]} for f in F.values()}


def hit(fid):
    f = F[fid]
    return {"title": f["page"].splitlines()[0], "url": f["url"], "snippet": f["page"][:120]}


def search_factory(first, later):
    def search(q):
        search.seen.append(q)
        return [hit(i) for i in (first if len(search.seen) == 1 else later)]
    search.seen = []
    return search


def show(name, r, search):
    print(f"\n== {name}\nfound={r.found} answer={r.answer!r}\nsource={r.source and r.source.url}"
          f"\nqueries={r.queries}\nopened={r.opened}\nmessage={r.message}")


# 1. answer on the second result of the first search
s = search_factory(["p03_ads_no", "p06_hours_yes"], [])
show("found first search", gather(F["p06_hours_yes"]["question"], s, PAGES.__getitem__, today=TODAY), s)

# 2. first search has only wrong pages; rephrased search finds it
s = search_factory(["p04_unrelated_no", "s07_similar_no"], ["s01_paraphrase_yes"])
show("found after rephrase", gather(F["s01_paraphrase_yes"]["question"], s, PAGES.__getitem__,
                                    today=TODAY), s)

# 3. nothing ever answers: gives up after 2 rephrases
s = search_factory(["p03_ads_no", "p05_login_no"], ["p04_unrelated_no", "s08_similar_no"])
show("gives up", gather("When are the CS 4110 TA office hours?", s, PAGES.__getitem__, today=TODAY), s)

print("\n== rephrase alone")
print(rephrase("Will it rain in Ithaca tomorrow afternoon?",
               ["Will it rain in Ithaca tomorrow afternoon?", "ithaca weather saturday"], today=TODAY))
