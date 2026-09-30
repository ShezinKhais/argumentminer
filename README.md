# ArgumentMiner

Analyses argumentative text - debates, opinion pieces, forum threads - and extracts the logical structure. It identifies claims, premises, and conclusions, detects support/attack relationships between them, flags logical fallacies, and renders everything as an interactive directed graph.

Built to explore how argument structure can be modelled programmatically and how rule-based NLP compares to trained models on structured reasoning tasks.

---

## How it works

1. Input text is split into argument units (sentences or clauses) and classified as claim, premise, or conclusion using marker phrase patterns
2. Consecutive unit pairs are checked for support or attack relationships using a second set of patterns
3. Eight fallacy detectors run over each unit: Ad Hominem, Appeal to Popularity, False Dichotomy, Appeal to Authority, Slippery Slope, Straw Man, Hasty Generalisation, Appeal to Emotion
4. A directed graph is built from the units (nodes = argument units, edges = relations)
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
- Dashed line into a crossbar: an attack relation
- Rule at a unit's leading edge: its role
- Dotted underline in a unit's text: the phrase a fallacy detector matched
- Ring around a lane dot: at least one detector matched in that unit

The rail is dropped on narrow screens, where the words carry the relations. The
report fetches nothing and opens offline.

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
    └── test_fallacy.py
```

---

## Stack

Python 3.10, Typer, Rich. The HTML report is written by hand, with no
charting or graph library and no runtime download.
