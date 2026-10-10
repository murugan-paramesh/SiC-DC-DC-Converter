# Writing rules for the learning notes (binding for every chapter)

Audience: a reader who starts with basic physics/maths and wants to reach research level. Every
chapter is written on **three levels**, marked with these exact headings inside each topic:

* `**Level 1 - Beginner:**` plain words, an everyday analogy, no equations beyond V = I R.
* `**Level 2 - Engineering:**` the equations, the numbers of OUR converter, the design decision.
* `**Level 3 - Research:**` what the literature says, what is still open, how our 2026 modules treat it.

Every topic (component, equation, schematic sheet, PCB feature, algorithm, simulation) uses the
template below with the exact headings (so that the viva/interview sections can be found by scripts):

```
### <Topic name>
**What is it?** ...
**Why do we need it?** ...
**How does it work?** ...
**Example from our converter:** (quote the real value / file / figure)
**Engineering calculations:** (equation, numbers, units, source file)
**Design decision made in this project:** ...
**Alternatives considered:** ...
**How to verify it:** (simulation / test / measurement, and which file or script does it today)
**Common mistakes:** ...
**Interview explanation (30 s):** ...
**Research-level explanation:** ...
```

Every statement about THIS project must be traceable to a real file in the repository (give the
path) and carry one of the status tags, exactly as written: `[Implemented]`, `[Simulated]`,
`[Verified]` (a check that runs and passes), `[Proposed]`, `[Not yet tested]`. Nothing in this
repository is hardware-validated: never write that the converter was built, measured or certified.
Numbers come from the project files (design_values.json, control_params.json, results JSON, DRC
summaries, README tables); do not invent numbers. If a value is a datasheet-typical figure entered
from memory (devices.py says `verified=False`), say so.

Chapter skeleton:

```
# <NN> <Chapter title>

> Reading time: ~x min. Prerequisites: chapters ... Files covered: ...

## Overview (Level 1 in one paragraph, Level 2 in one paragraph, Level 3 in one paragraph)
## <Topics ...> (template per topic)
## Worked example(s) with real numbers
## How this chapter connects to the files
| File | What it contains | Status |
## Viva / interview questions
### Basic (10)  - question, then a 2-4 line model answer
### Intermediate (10)
### Advanced / research (10)
## Pitches
**30 s:** ...  **2 min:** ...  **10 min outline:** bullet list
## Further reading (only sources that exist; prefer the verified entries of
   Advanced_Research_2026/Literature_Database/literature_2022_2026.csv by id)
```

Markdown only, ASCII punctuation, no HTML. Figures: reference existing PNGs with relative paths
(e.g. `../SiC_6k6_Industrial_DAB/05_Simulation/img/sim_startup_loadstep.png`); if a new sketch is
needed, make it with matplotlib into `21_Human_Friendly_Learning_Notes/img/` with a script in the
same folder. No vendor/AI-tool identifiers. Length guide: 2500-5000 words per chapter.
