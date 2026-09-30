# Kakarot Todo

A local-first daily todo TUI built with Python, Textual and SQLite.

## Install

```bash
cd kakarot-todo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Keys

- `↑/↓` — select task
- `Space` — complete/uncomplete selected task
- `←/→` — move selected date
- `PageUp/PageDown` — change calendar month
- `t` — jump to today
- `a` — add task
- `d` — delete selected task
- `q` — quit

## Adding tasks

Press `a`, type a task, and press Enter.

Normal task:

```text
Finish DB diagram
```

Daily recurring task:

```text
daily: LeetCode
```

The calendar stays on the same screen. Daily tasks are pre-created for the next 120 days and are stored locally in:

```text
~/.kakarot-todo/todo.db
```
# streaky
