# Streaky

**Streaky** is a terminal-first daily task manager built with **Python, Textual, and SQLite**.

It combines a simple daily task list with:

- daily and recurring tasks
- task completion tracking
- a GitHub-style activity heatmap
- current streak tracking
- holidays that do not break a streak
- optional task notes
- delete confirmation
- an all-tasks screen
- a local SQLite database

> **Streaky — Your tasks. Your streak. Your progress.**

## Features

### Daily and recurring tasks

Press `a` to add a task.

The add dialog lets you choose:

- **One-time** — creates a task for the selected day.
- **Repeat every day** — creates daily occurrences for the task.

### Completion tracking

Select a task and press `Space` to toggle completion.

Completed tasks are shown with `✓`.

### Delete confirmation

Press `d`.

Streaky asks for confirmation before deleting the selected task.

### Holidays

Press `h` on the selected day.

Streaky asks:

```text
Mark this day as a holiday?
Carry unfinished tasks to the next day?
```

Choose:

- **Yes** — unfinished one-time tasks are moved to tomorrow.
- **No** — unfinished tasks remain on the holiday.
- `Esc` — same as No.

Recurring tasks are not duplicated because the next recurring occurrence already exists.

Holiday days are skipped when calculating the current streak, so a planned day off does not break your streak.

### Task notes

Select a task and edit the **Notes for selected task** field below the calendar.

Press `Ctrl+S` to save the notes.

Notes are stored locally in SQLite.

### GitHub-style activity

The dashboard contains a 12-week contribution-style activity graph.

Each square represents one day. The activity level is based on the number of tasks completed that day.

This is inspired by GitHub's contribution graph; it does not connect to GitHub.

### Streak

The current streak counts consecutive non-holiday days with at least one completed task.

Example:

```text
Mon  completed
Tue  completed
Wed  holiday
Thu  completed
Fri  completed
```

The current streak is `4`, because the holiday is skipped.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `a` | Add task |
| `d` | Delete selected task |
| `h` | Mark/unmark holiday |
| `Space` | Complete/uncomplete selected task |
| `Ctrl+S` | Save task notes |
| `←` | Previous day |
| `→` | Next day |
| `l` | Open all tasks |
| `Esc` | Leave All Tasks |
| `q` | Quit |

## Requirements

- Python 3.10+
- Textual
- SQLite

SQLite is normally included with Python.

## Setup

Streaky uses the `setup/` scripts for installation and updates.

### Install

From the project directory:

```bash
./setup/install
```

The installer:

1. Checks whether `uv` is installed.
2. Offers to install `uv` if it is missing.
3. Checks whether the `streaky` command is already installed.
4. If Streaky is already installed, asks whether it should be updated.
5. Otherwise, asks whether Streaky should be installed.

After installation:

```bash
streaky
```

### Update

Run:

```bash
./setup/update
```

The updater:

1. Checks whether `uv` is available.
2. Checks whether the `streaky` command exists.
3. If Streaky is not installed, asks whether to install it.
4. If Streaky is installed, asks whether to update it.
5. Reinstalls the current source with `uv tool install --force .`.

### Setup layout

```text
setup/
├── install
└── update
```

This keeps installation and update commands separate while keeping all setup logic inside the `setup/` directory.

## Installation

Streaky is designed to work well with `uv`.

### Install uv

On Arch/Garuda Linux:

```bash
sudo pacman -S uv
```

### Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/streaky.git
cd streaky
```

### Install dependencies

```bash
uv sync
```

### Run

```bash
uv run streaky
```

## Install Streaky as a terminal command

From the project directory:

```bash
uv tool install .
```

Then run:

```bash
streaky
```

After changing the source code, reinstall the tool:

```bash
uv tool install --force .
```

Remove it with:

```bash
uv tool uninstall streaky
```

## Development

Run Streaky without installing the command globally:

```bash
uv run streaky
```

The main application is:

```text
app.py
```

The CLI entry point is defined in:

```text
pyproject.toml
```

```toml
[project.scripts]
streaky = "app:main"
```


## Storage information

Streaky keeps its task data locally, similar to how Taskwarrior exposes its data location.

Run:

```bash
streaky show
```

Example:

```text
Streaky storage
----------------
Data directory : /home/your-user/.streaky
Database       : /home/your-user/.streaky/streaky.db
Database exists: yes

Source/config
-------------
Application    : installed through uv tool
Project source : the directory from which Streaky was installed

Commands
--------
streaky        Start the TUI
streaky show   Show storage information
```

The exact path is automatically based on your home directory.

## Data storage

Streaky stores everything locally.

Database:

```text
~/.streaky/streaky.db
```

No account, cloud service, or external database is required.

To completely reset Streaky, remove:

```bash
rm ~/.streaky/streaky.db
```

**Warning:** this permanently removes your local tasks, notes, completion history, and holidays.

## Project structure

```text
streaky/
├── app.py
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
└── LICENSE
```

## GitHub setup

Before publishing:

1. Create a GitHub repository named `streaky`.
2. Replace `YOUR_USERNAME` in this README.
3. Review the project description.
4. Commit the source.
5. Push the repository.
6. Create a release such as `v0.6.0`.

Suggested GitHub description:

> A terminal-first daily task manager with streaks, holidays, notes, and a GitHub-style activity graph.

Suggested topics:

```text
python
textual
tui
terminal
todo
task-manager
productivity
sqlite
streak
```

## Roadmap

Possible future improvements:

- monthly and yearly calendar navigation
- task editing
- priorities and tags
- configurable recurring schedules
- configurable streak rules
- export/import
- JSON backup
- better themes
- mouse support
- optional notifications
- statistics page

## License

MIT License. See `LICENSE`.
