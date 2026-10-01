# ArgumentMiner

Analyses argumentative text - debates, opinion pieces, forum threads - and extracts the logical structure. It identifies claims, premises and conclusions, links them into a directed graph of support relations, flags the phrasing of eight logical fallacies, and renders the result as a self-contained HTML report.

Built to explore how argument structure can be modelled programmatically and how rule-based NLP compares to trained models on structured reasoning tasks.

---

## How it works

1. Input text is split into argument units (sentences or clauses) and classified as claim, premise, or conclusion using marker phrase patterns
2. A premise is attached as support to the most recent preceding claim, and a claim is attached as support to a conclusion that follows it. Nothing else creates a relation, so a passage with no claim has no relations at all
3. Eight fallacy detectors run over each unit: Ad Hominem, Straw Man, Appeal to Authority, False Dichotomy, Slippery Slope, Appeal to Emotion, Circular Reasoning, Hasty Generalization
4. A directed graph is built from the units: nodes are argument units, edges are support relations
5. The graph is rendered as a self-contained HTML report with no external requests

---

## Usage

```bash
pip install -r requirements.txt

python -m argumentminer.cli mine "text to analyse"
# or from a file:
python -m argumentminer.cli mine --file debate.txt

# just list the fallacies, without building a graph:
python -m argumentminer.cli fallacies "text to analyse"
```

`mine` prints a terminal table of argument units and fallacies and can save an
HTML graph with `--html`. `fallacies` runs only the fallacy detectors.

---

## Report legend

The HTML report lists the units in the order they appear in the source, with a
rail on the left that places each one in its role's lane: background, premise,
claim, conclusion, left to right. Relations are drawn across the rail and are
also written out in words on each unit, so nothing depends on seeing the
drawing.

- Solid line into an arrowhead: a support relation, drawn from the supporting
  unit to the unit it supports
- Dashed line into a crossbar: an attack relation. The report can draw one,
  but no rule currently emits one, so you will not see it on real input
- Rule at a unit's leading edge: its role
- Dotted underline in a unit's text: the phrase a fallacy detector matched
- Ring around a lane dot: at least one detector matched in that unit

The rail is dropped on narrow screens, where the words carry the relations. The
report fetches nothing and opens offline.

---

## Limitations

Everything here is pattern matching over surface text, and the output should
be read as somewhere to look rather than as a verdict.

- Each detector is a single marker phrase pattern. A match means the phrase
  occurred, not that the argument commits the fallacy. Quotation, reported
  speech and ordinary usage trip the same patterns, so expect false positives.
  The report says so on the page as well.
- The confidence beside a fallacy is a constant written into the detector. It
  is identical for every match that detector ever makes, so it ranks the
  detectors against each other and measures nothing about the passage in hand.
- A fallacy committed without its usual phrasing is invisible. There is no
  model behind this, only the eight patterns listed above.
- Support is the only relation the graph builder emits. Attack is in the data
  model and the report can draw one, but no rule creates it, so a rebuttal is
  recorded as an unrelated unit rather than as an attack.
- Relations are anchored on the most recent claim. A premise that supports a
  claim made earlier than the last one is attached to the wrong claim, and a
  passage containing no claim at all comes out with no relations.
- Unit roles come from marker phrases too, which means a claim introduced
  without one ("Therefore", "because", "I think") falls back to being read as
  background.

---
## Testing

Install the dependencies and run the suite:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt pytest   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -v
```

Exercise the CLI directly with `python -m argumentminer.cli --help`.

---

## Project structure

```
argumentminer/
├── argumentminer/
│   ├── segmenter.py    # argument unit classification
│   ├── fallacy.py      # 8 fallacy pattern detectors
│   ├── graph.py        # support/attack relations, graph construction
│   ├── visualiser.py   # text tree and self-contained HTML report
│   └── cli.py
└── tests/
    ├── test_segmenter.py  # unit classification and the HTML report
    ├── test_fallacy.py
    └── test_cli.py
```

---

## Stack

Python 3.10, Typer, Rich. The HTML report is written by hand, with no
charting or graph library and no runtime download.
