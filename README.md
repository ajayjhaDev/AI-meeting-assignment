# AI-meeting-assignment

# PSI Sprint Status Reporter

A small utility that turns raw sprint metrics into a leadership-ready weekly status report, so a Technical Project Manager does not have to rebuild the same report by hand every week.

## What it does
- Reads sprint metrics from a JSON file (sprint progress, velocity, bugs, milestones, risks, blockers, budget)
- Computes an explainable RAG health status (GREEN / AMBER / RED) with the reasons listed
- Writes `report.md` and a styled `report.html`
- Optional `--ai` flag adds an executive narrative written by the Claude API

## Setup
Requires Python 3.8+. There are no third-party dependencies.

```bash
git clone <your-repo-url>
cd psi-status-reporter
python app.py sample_data.json
```
Open `report.html` in a browser.

### Optional AI narrative
```bash
export ANTHROPIC_API_KEY=your_key_here
python app.py sample_data.json --ai
```
The model can be changed with `ANTHROPIC_MODEL`. If the key is missing or the call fails, the report still generates.

## Input format
See `sample_data.json`. Replace the mock values with exports from Jira or your tracker.

## Health rules (see `compute_health` in app.py)
| Signal | Amber | Red |
|---|---|---|
| Pace vs plan | below 90% | below 70% |
| Open high-severity risks (15+) | 1-2 | 3 or more |
| Critical bugs | | any |
| Unresolved blockers | | 3 or more |
| Milestones at risk | any | |
Score of 2+ is AMBER, 4+ is RED.

## AI workflow used to build this
1. Described the repetitive task to Claude: "I rebuild a weekly status report for leadership every Friday from Jira numbers."
2. Asked for transparent health rules instead of a black-box score, then reviewed and tuned the thresholds.
3. Asked Claude to add an optional LLM narrative with a graceful offline fallback.
4. Tested against mock Sprint 3 data and iterated on the output layout.

## Future improvements
Jira API import, trend charts, Slack posting of the weekly report.