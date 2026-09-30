# Kakarot Todo V3

A simple local-first daily todo TUI built with Python, Textual and SQLite.

## What's new in V3

- Added a separate **All Tasks** page.
- Press `l` to open All Tasks.
- Press `Esc` or `q` to return to the main page.
- All stored tasks are grouped by date.
- Completed tasks are shown with `✓`.
- Recurring tasks are marked with `🔁 daily`.
- Holidays are shown with a **subtle light-red background** in the calendar.
- Press `h` on a selected date to mark/unmark it as a holiday.
- Holiday dates are also labelled on the All Tasks page.

## Run with uv

```bash
uv venv
uv pip install -r requirements.txt
uv run python app.py
```

Or install the project as a command:

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
| `l` | Open All Tasks page |
| `t` | Jump to today |
| `d` | Delete selected task |
| `q` | Quit / leave All Tasks page |
| `Esc` | Leave All Tasks page |

## Database

The application stores data locally at:

```text
~/.kakarot-todo/todo.db
```

No cloud service is required.
