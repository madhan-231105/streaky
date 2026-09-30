# Streaky

**Your tasks. Your streak. Your progress.**

Streaky is a simple terminal-based daily task manager that helps you keep track of your tasks and build consistent habits.

It works completely locally, so your tasks stay on your computer.

## Features

* 📋 Daily tasks
* 🔁 Daily recurring tasks
* ✓ Task completion tracking
* 🔥 Current streak
* 🏖️ Holidays that don't break your streak
* 📝 Notes for tasks
* 📊 12-week activity graph
* 📅 Calendar view
* 📚 All tasks view
* 💾 Local data storage
* 🖥️ Terminal-based interface

## Getting Started

### Add a task

Press:

```text
a
```

Enter your task and choose whether it should repeat every day.

You can create:

* **One-time tasks** — appear only on the selected day
* **Daily tasks** — repeat every day

### Complete a task

Select a task and press:

```text
Space
```

Completed tasks are shown with:

```text
✓
```

Press `Space` again to mark the task as incomplete.

### Delete a task

Select a task and press:

```text
d
```

Streaky will ask for confirmation before deleting it.

## Holidays

Have a day off?

Press:

```text
h
```

Streaky will ask:

```text
Mark this day as a holiday?
Carry unfinished tasks to the next day?
```

Choose **Yes** to move unfinished one-time tasks to tomorrow.

Choose **No** to leave them on the holiday.

Holiday days don't break your streak.

For example:

```text
Monday     ✓
Tuesday    ✓
Wednesday  Holiday
Thursday   ✓
Friday     ✓
```

Your streak is:

```text
🔥 4 days
```

Recurring tasks aren't copied when tasks are carried forward because their next occurrence already exists.

Press `h` again to remove a holiday.

## Task Notes

Select a task and use the notes area below the calendar to add or edit notes.

Press:

```text
Ctrl+S
```

to save your notes.

## Activity

Streaky includes a 12-week activity graph showing how many tasks you've completed each day.

More completed tasks on a day means a higher activity level.

```text
■ ■ ■ ■ ■ ■ ■
■ ■ ■ ■ ■ ■ ■
■ ■ ■ ■ ■ ■ ■
```

The graph is inspired by GitHub's contribution graph, but Streaky does **not** connect to GitHub.

## Your Streak

Your current streak counts consecutive days where you completed at least one task.

Holiday days are skipped.

A day without any completed task breaks the streak.

## Calendar

Use the calendar to quickly see your progress.

The calendar shows:

* **Selected day**
* **Holiday**
* **Completed days**
* **Days with tasks**
* **Empty days**

Use the arrow keys to move between days.

```text
← Previous day
→ Next day
```

## All Tasks

Press:

```text
l
```

to see all your tasks grouped by date.

Press:

```text
Esc
```

to return to the main screen.

## Keyboard Shortcuts

| Key      | Action                   |
| -------- | ------------------------ |
| `a`      | Add task                 |
| `d`      | Delete task              |
| `h`      | Mark/unmark holiday      |
| `Space`  | Complete/uncomplete task |
| `Ctrl+S` | Save notes               |
| `←`      | Previous day             |
| `→`      | Next day                 |
| `l`      | View all tasks           |
| `Esc`    | Go back / cancel         |
| `q`      | Quit                     |

## Installation

### Requirements

* Python 3.10+
* `uv`

SQLite is included with Python.

### Install `uv`

On Arch Linux / Garuda Linux:

```bash
sudo pacman -S uv
```

### Install Streaky

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/streaky.git
cd streaky
```

Then install it:

```bash
uv tool install .
```

Start Streaky:

```bash
streaky
```

## Running Without Installing

If you're working on the project or just want to try it without installing the command globally:

```bash
uv sync
uv run streaky
```

## Updating

If you already have Streaky installed and have downloaded a newer version:

```bash
uv tool install --force .
```

If the project includes the setup scripts, you can also use:

```bash
./setup/update
```

## Storage

Your data is stored locally at:

```text
~/.streaky/streaky.db
```

You don't need an account or an internet connection to use Streaky.

### Check Storage Location

Run:

```bash
streaky show
```

This displays where Streaky stores your data.

## Reset Streaky

To completely reset your data:

```bash
rm ~/.streaky/streaky.db
```

> ⚠️ This permanently deletes your tasks, notes, completion history, recurring tasks, and holidays.

## Commands

Start Streaky:

```bash
streaky
```

Show storage information:

```bash
streaky show
```

Show the version:

```bash
streaky --version
```

Show help:

```bash
streaky --help
```

## License

MIT License.

See [`LICENSE`](LICENSE) for details.
