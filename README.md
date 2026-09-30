# Kakarot Todo V4

A simple local-first daily todo TUI built with Python, Textual and SQLite.

## What's new in V4

- `l` opens the **All Tasks** page.
- `Esc`, `q`, or `l` returns from **All Tasks**.
- All Tasks is kept simple: dates are grouped, with compact task rows.
- Marking a date as a holiday asks:
  **"Move incomplete tasks to the next day?"**
- `Y` carries incomplete tasks forward.
- `N` or `Esc` keeps the tasks on the holiday date.
- For recurring tasks, the existing next-day recurring occurrence is used, so duplicates are not created.
- Holidays keep their subtle light-red calendar background.

## Run

```bash
uv venv
uv pip install -r requirements.txt
uv run python app.py
```

Or:

```bash
uv pip install -e .
uv run kakarot-todo
```

## Controls

| Key | Action |
|---|---|
| `↑ / ↓` | Move between tasks |
| `← / →` | Previous/next day |
| `PageUp / PageDown` | Previous/next month |
| `Space` | Complete/uncomplete task |
| `a` | Add task |
| `h` | Mark/unmark holiday |
| `l` | Open All Tasks / return from All Tasks |
| `t` | Jump to today |
| `d` | Delete selected task |
| `q` | Quit / return from All Tasks |
| `Esc` | Return from All Tasks |

Database:

```text
~/.kakarot-todo/todo.db
```
