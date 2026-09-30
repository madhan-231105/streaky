# Kakarot Todo

A small, local-first TUI todo application built with **Python, Textual, and SQLite**.

The goal is to keep the code simple enough to understand and extend.

## Features

- Tasks stored locally in SQLite
- One-time tasks
- Daily recurring tasks
- Add-task dialog with a **Repeat every day** checkbox
- Same-page monthly calendar
- Date navigation
- Holiday/excluded-day marking
- Completion history
- No cloud account required

## Project structure

```text
kakarot-todo/
├── app.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

The application database is created automatically at:

```text
~/.kakarot-todo/todo.db
```

## Run with uv

```bash
uv venv
uv pip install -r requirements.txt
uv run python app.py
```

## Run as a CLI

After installing the project:

```bash
uv pip install -e .
```

you can run:

```bash
uv run kakarot-todo
```

## Controls

| Key | Action |
|---|---|
| `↑` / `↓` | Select task |
| `Space` | Complete / uncomplete |
| `←` / `→` | Previous / next day |
| `PageUp` / `PageDown` | Previous / next month |
| `t` | Jump to today |
| `a` | Add task |
| `h` | Mark/unmark holiday |
| `d` | Delete selected task |
| `q` | Quit |

## Adding a task

Press `a`.

The dialog contains:

```text
Add Task

Task name: [________________]

☐ Repeat every day

Enter = Save   Esc = Cancel
```

If **Repeat every day** is checked, the task is created as a daily recurring task.

If it is unchecked, the task is only created for the selected date.

## Holidays and streaks

Press `h` while a date is selected to mark it as a holiday.

A holiday is an explicitly excluded day. It is stored in the database so future streak calculations can skip that date rather than treating it as a missed day.

**Important:** the current V2 stores holidays and displays them in the calendar. A dedicated streak calculation is intentionally left for the next feature, so the streak logic can be implemented separately and clearly.

## License

Choose the license you want before publishing the repository.
