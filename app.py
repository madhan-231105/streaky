from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static


APP_DIR = Path.home() / ".kakarot-todo"
DB_PATH = APP_DIR / "todo.db"


class TodoDB:
    """Small SQLite database used by Kakarot Todo."""

    def __init__(self, path: Path = DB_PATH):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recurring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                recurrence TEXT NOT NULL DEFAULT 'daily',
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                recurring_id INTEGER,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(recurring_id) REFERENCES recurring(id)
            );

            CREATE TABLE IF NOT EXISTS holidays (
                holiday_date TEXT PRIMARY KEY,
                note TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_recurring_daily_occurrence
                ON tasks(recurring_id, due_date)
                WHERE recurring_id IS NOT NULL;
            """
        )
        self.ensure_recurring_occurrences()

    # ---------- Tasks ----------

    def ensure_recurring_occurrences(self, days: int = 120) -> None:
        """Keep future daily occurrences available in the task table."""
        today = date.today()
        recurring = self.conn.execute(
            "SELECT id, title, recurrence FROM recurring WHERE active = 1"
        ).fetchall()

        for item in recurring:
            if item["recurrence"] != "daily":
                continue

            for offset in range(days):
                due = today + timedelta(days=offset)
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks
                    (title, due_date, completed, recurring_id, created_at)
                    VALUES (?, ?, 0, ?, ?)
                    """,
                    (
                        item["title"],
                        due.isoformat(),
                        item["id"],
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )

        self.conn.commit()

    def add_daily(self, title: str) -> None:
        """Create a daily recurring task and its next 120 occurrences."""
        cur = self.conn.execute(
            "INSERT INTO recurring(title, recurrence) VALUES (?, 'daily')",
            (title,),
        )
        recurring_id = cur.lastrowid
        today = date.today()

        for offset in range(120):
            due = today + timedelta(days=offset)
            self.conn.execute(
                """
                INSERT OR IGNORE INTO tasks
                (title, due_date, recurring_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    title,
                    due.isoformat(),
                    recurring_id,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

        self.conn.commit()

    def add_one_time(self, title: str, due: date) -> None:
        self.conn.execute(
            """
            INSERT INTO tasks(title, due_date, created_at)
            VALUES (?, ?, ?)
            """,
            (title, due.isoformat(), datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def tasks_for(self, due: date):
        return self.conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE due_date = ?
            ORDER BY completed ASC, recurring_id IS NULL ASC, id ASC
            """,
            (due.isoformat(),),
        ).fetchall()

    def all_tasks(self):
        """Return every task, ordered by date and completion state."""
        return self.conn.execute(
            """
            SELECT *
            FROM tasks
            ORDER BY due_date ASC, completed ASC, recurring_id IS NULL ASC, id ASC
            """
        ).fetchall()

    def toggle(self, task_id: int) -> None:
        row = self.conn.execute(
            "SELECT completed FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if not row:
            return

        completed = 0 if row["completed"] else 1
        completed_at = (
            datetime.now().isoformat(timespec="seconds")
            if completed
            else None
        )

        self.conn.execute(
            """
            UPDATE tasks
            SET completed = ?, completed_at = ?
            WHERE id = ?
            """,
            (completed, completed_at, task_id),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def counts_for_month(self, year: int, month: int):
        """Return pending/completed counts for each date in a month."""
        month_start = date(year, month, 1)
        month_end = (
            date(year + 1, 1, 1)
            if month == 12
            else date(year, month + 1, 1)
        )

        rows = self.conn.execute(
            """
            SELECT
                due_date,
                SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed
            FROM tasks
            WHERE due_date >= ? AND due_date < ?
            GROUP BY due_date
            """,
            (month_start.isoformat(), month_end.isoformat()),
        ).fetchall()

        return {
            row["due_date"]: (row["pending"], row["completed"])
            for row in rows
        }

    # ---------- Holidays ----------

    def set_holiday(self, holiday: date, note: str = "") -> None:
        self.conn.execute(
            """
            INSERT INTO holidays(holiday_date, note)
            VALUES (?, ?)
            ON CONFLICT(holiday_date)
            DO UPDATE SET note = excluded.note
            """,
            (holiday.isoformat(), note),
        )
        self.conn.commit()

    def remove_holiday(self, holiday: date) -> None:
        self.conn.execute(
            "DELETE FROM holidays WHERE holiday_date = ?",
            (holiday.isoformat(),),
        )
        self.conn.commit()

    def is_holiday(self, holiday: date) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM holidays WHERE holiday_date = ?",
            (holiday.isoformat(),),
        ).fetchone()
        return row is not None

    # ---------- Statistics ----------

    def stats(self):
        today = date.today().isoformat()

        pending = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM tasks
            WHERE due_date = ? AND completed = 0
            """,
            (today,),
        ).fetchone()["n"]

        completed = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM tasks
            WHERE due_date = ? AND completed = 1
            """,
            (today,),
        ).fetchone()["n"]

        return pending, completed


class CalendarWidget(Static):
    """Month calendar displayed on the right side of the main page."""

    def __init__(self, app: "KakarotTodo"):
        super().__init__()
        self.todo_app = app

    def render(self) -> Text:
        app = self.todo_app
        year = app.calendar_month.year
        month = app.calendar_month.month

        task_counts = app.db.counts_for_month(year, month)
        weeks = calendar.monthcalendar(year, month)

        output = Text()
        title = f"{calendar.month_name[month]} {year}"
        output.append(title.center(28) + "\n", style="bold")
        output.append("Mo Tu We Th Fr Sa Su\n", style="dim")

        for week in weeks:
            for day in week:
                if day == 0:
                    output.append("   ")
                    continue

                current = date(year, month, day)
                key = current.isoformat()
                pending, completed = task_counts.get(key, (0, 0))

                selected = current == app.selected_date
                today = current == date.today()
                holiday = app.db.is_holiday(current)

                label = f"{day:2d}"

                # Holidays get a subtle light-red background.
                if selected and holiday:
                    style = "bold black on #8f4f4f"
                    output.append(f"[{label}]", style=style)
                elif selected:
                    output.append(f"[{label}]", style="bold reverse")
                elif holiday:
                    output.append(label, style="bold black on #8f4f4f")
                elif today:
                    output.append(label, style="bold underline")
                elif pending:
                    output.append(label, style="bold")
                else:
                    output.append(label)

                output.append(" ")

            output.append("\n")

        output.append("\n")
        output.append("● ", style="bold")
        output.append("tasks due  ")
        output.append("✓ ", style="bold")
        output.append("completed  ")
        output.append("■ ", style="bold black on #8f4f4f")
        output.append("holiday  ")
        output.append("[] ", style="reverse")
        output.append("selected")

        return output


class AllTasksScreen(Screen):
    """Separate page containing every stored task."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def __init__(self, db: TodoDB):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="all_tasks_page"):
            yield Static("All Tasks", id="all_tasks_title")
            yield Static(
                "Every task in the database • completed and pending",
                id="all_tasks_subtitle",
            )
            yield VerticalScroll(id="all_tasks_list")

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        task_list = self.query_one("#all_tasks_list", VerticalScroll)
        task_list.remove_children()

        tasks = self.db.all_tasks()

        if not tasks:
            task_list.mount(
                Static(
                    "No tasks yet.",
                    classes="all_task_row",
                )
            )
            return

        current_date = None

        for task in tasks:
            task_date = date.fromisoformat(task["due_date"])

            if task_date != current_date:
                current_date = task_date
                holiday_text = "  • HOLIDAY" if self.db.is_holiday(task_date) else ""

                task_list.mount(
                    Static(
                        f"{task_date.strftime('%A, %d %B %Y')}{holiday_text}",
                        classes="date_group",
                    )
                )

            prefix = "✓" if task["completed"] else "☐"
            recurring = "  🔁 daily" if task["recurring_id"] else ""
            text = f"{prefix}  {task['title']}{recurring}"

            classes = "all_task_row"
            if task["completed"]:
                classes += " completed"

            task_list.mount(Static(text, classes=classes))

    def action_back(self) -> None:
        self.app.pop_screen()


class KakarotTodo(App):
    TITLE = "Kakarot Todo"

    CSS = """
    Screen {
        background: #0b0b0b;
        color: #e8e8e8;
    }

    #main {
        height: 1fr;
    }

    #tasks_panel {
        width: 60%;
        border: round #444444;
        padding: 1 2;
    }

    #calendar_panel {
        width: 40%;
        border: round #444444;
        padding: 1 2;
    }

    #task_header {
        height: 3;
        text-style: bold;
    }

    #task_list {
        height: 1fr;
    }

    .task_row {
        height: 2;
        padding: 0 1;
    }

    .selected_task {
        background: #333333;
        color: white;
        text-style: bold;
    }

    .completed {
        color: #777777;
        text-style: strike;
    }

    #add_input {
        display: none;
        height: 3;
        margin-top: 1;
    }

    #status {
        height: 3;
        border-top: solid #444444;
        padding: 0 2;
        content-align: center middle;
    }

    /* ---------- All Tasks page ---------- */

    #all_tasks_page {
        height: 1fr;
        padding: 1 2;
    }

    #all_tasks_title {
        height: 3;
        text-style: bold;
        content-align: center middle;
    }

    #all_tasks_subtitle {
        height: 2;
        color: #999999;
        content-align: center middle;
    }

    #all_tasks_list {
        height: 1fr;
        border: round #444444;
        padding: 1 2;
    }

    .date_group {
        height: 2;
        margin-top: 1;
        color: #e8e8e8;
        text-style: bold underline;
    }

    .all_task_row {
        height: 2;
        padding: 0 2;
    }

    Footer {
        background: #111111;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("up", "prev_task", "Task ↑"),
        ("down", "next_task", "Task ↓"),
        ("space", "toggle_task", "Complete"),
        ("left", "prev_day", "Date ←"),
        ("right", "next_day", "Date →"),
        ("pageup", "prev_month", "Month ←"),
        ("pagedown", "next_month", "Month →"),
        ("a", "add_task", "Add"),
        ("d", "delete_task", "Delete"),
        ("h", "toggle_holiday", "Holiday"),
        ("l", "all_tasks", "All Tasks"),
        ("t", "today", "Today"),
    ]

    def __init__(self):
        super().__init__()
        self.db = TodoDB()
        self.selected_date = date.today()
        self.calendar_month = date.today().replace(day=1)
        self.selected_task_index = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main"):
            with Vertical(id="tasks_panel"):
                yield Static(id="task_header")
                yield VerticalScroll(id="task_list")
                yield Input(
                    placeholder="Type task and press Enter (prefix 'daily:' for recurring)",
                    id="add_input",
                )

            with Vertical(id="calendar_panel"):
                yield CalendarWidget(self)
                yield Static(id="status")

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        tasks = self.db.tasks_for(self.selected_date)

        header = self.query_one("#task_header", Static)
        holiday_text = "  • HOLIDAY" if self.db.is_holiday(self.selected_date) else ""
        header.update(
            f"{self.selected_date.strftime('%A, %d %B %Y')}{holiday_text}\n"
            "Today-first task list"
        )

        task_list = self.query_one("#task_list", VerticalScroll)
        task_list.remove_children()

        if not tasks:
            task_list.mount(
                Static(
                    "No tasks for this date.\nPress 'a' to add one.",
                    classes="task_row",
                )
            )
        else:
            for index, task in enumerate(tasks):
                prefix = "✓" if task["completed"] else "☐"
                recurring = "  🔁 daily" if task["recurring_id"] else ""
                text = f"{prefix}  {task['title']}{recurring}"

                classes = "task_row"
                if task["completed"]:
                    classes += " completed"
                if index == self.selected_task_index:
                    classes += " selected_task"

                task_list.mount(Static(text, classes=classes))

        pending, completed = self.db.stats()
        status = self.query_one("#status", Static)
        status.update(
            f"Today: {completed} completed  •  {pending} pending"
            "   |  ←→ date  ↑↓ task  Space complete"
            "  a add  h holiday  l all tasks"
        )

        self.query_one(CalendarWidget).refresh()

    def current_tasks(self):
        return self.db.tasks_for(self.selected_date)

    # ---------- Task navigation ----------

    def action_prev_task(self) -> None:
        tasks = self.current_tasks()
        if tasks:
            self.selected_task_index = max(0, self.selected_task_index - 1)
            self.refresh_view()

    def action_next_task(self) -> None:
        tasks = self.current_tasks()
        if tasks:
            self.selected_task_index = min(
                len(tasks) - 1,
                self.selected_task_index + 1,
            )
            self.refresh_view()

    def action_toggle_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return

        task = tasks[self.selected_task_index]
        self.db.toggle(task["id"])
        self.refresh_view()

    # ---------- Date navigation ----------

    def move_date(self, delta: int) -> None:
        self.selected_date += timedelta(days=delta)
        self.calendar_month = self.selected_date.replace(day=1)
        self.selected_task_index = 0
        self.refresh_view()

    def action_prev_day(self) -> None:
        self.move_date(-1)

    def action_next_day(self) -> None:
        self.move_date(1)

    def action_prev_month(self) -> None:
        first = self.calendar_month

        if first.month == 1:
            self.calendar_month = date(first.year - 1, 12, 1)
        else:
            self.calendar_month = date(first.year, first.month - 1, 1)

        self.query_one(CalendarWidget).refresh()

    def action_next_month(self) -> None:
        first = self.calendar_month

        if first.month == 12:
            self.calendar_month = date(first.year + 1, 1, 1)
        else:
            self.calendar_month = date(first.year, first.month + 1, 1)

        self.query_one(CalendarWidget).refresh()

    def action_today(self) -> None:
        self.selected_date = date.today()
        self.calendar_month = date.today().replace(day=1)
        self.selected_task_index = 0
        self.refresh_view()

    # ---------- Add task ----------

    def action_add_task(self) -> None:
        input_box = self.query_one("#add_input", Input)
        input_box.display = True
        input_box.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()

        event.input.value = ""
        event.input.display = False

        if not value:
            self.refresh_view()
            return

        if value.lower().startswith("daily:"):
            title = value[6:].strip()
            if title:
                self.db.add_daily(title)
        else:
            self.db.add_one_time(value, self.selected_date)

        self.selected_task_index = 0
        self.refresh_view()

    # ---------- Holiday ----------

    def action_toggle_holiday(self) -> None:
        if self.db.is_holiday(self.selected_date):
            self.db.remove_holiday(self.selected_date)
        else:
            self.db.set_holiday(self.selected_date)

        self.refresh_view()

    # ---------- Delete ----------

    def action_delete_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return

        task = tasks[self.selected_task_index]
        self.db.delete_task(task["id"])

        self.selected_task_index = max(
            0,
            self.selected_task_index - 1,
        )
        self.refresh_view()

    # ---------- All tasks page ----------

    def action_all_tasks(self) -> None:
        self.push_screen(AllTasksScreen(self.db))


def main() -> None:
    KakarotTodo().run()


if __name__ == "__main__":
    main()
