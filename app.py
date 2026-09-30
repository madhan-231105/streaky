from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static


APP_DIR = Path.home() / ".kakarot-todo"
DB_PATH = APP_DIR / "todo.db"


class TodoDB:
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

            CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_recurring_daily_occurrence
                ON tasks(recurring_id, due_date)
                WHERE recurring_id IS NOT NULL;
            """
        )
        self.ensure_recurring_occurrences()

    def ensure_recurring_occurrences(self, days: int = 120) -> None:
        today = date.today()
        recurring = self.conn.execute(
            "SELECT id, title, recurrence FROM recurring WHERE active = 1"
        ).fetchall()

        for item in recurring:
            if item["recurrence"] != "daily":
                continue
            for offset in range(days):
                d = today + timedelta(days=offset)
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks
                    (title, due_date, completed, recurring_id, created_at)
                    VALUES (?, ?, 0, ?, ?)
                    """,
                    (
                        item["title"],
                        d.isoformat(),
                        item["id"],
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        self.conn.commit()

    def add_daily(self, title: str) -> None:
        cur = self.conn.execute(
            "INSERT INTO recurring(title, recurrence) VALUES (?, 'daily')",
            (title,),
        )
        rid = cur.lastrowid
        today = date.today()
        for offset in range(120):
            d = today + timedelta(days=offset)
            self.conn.execute(
                """
                INSERT OR IGNORE INTO tasks
                (title, due_date, recurring_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    title,
                    d.isoformat(),
                    rid,
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

    def tasks_for(self, d: date):
        return self.conn.execute(
            """
            SELECT * FROM tasks
            WHERE due_date = ?
            ORDER BY completed ASC, recurring_id IS NULL ASC, id ASC
            """,
            (d.isoformat(),),
        ).fetchall()

    def toggle(self, task_id: int) -> None:
        row = self.conn.execute(
            "SELECT completed FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return
        new_value = 0 if row["completed"] else 1
        self.conn.execute(
            """
            UPDATE tasks
            SET completed = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                new_value,
                datetime.now().isoformat(timespec="seconds") if new_value else None,
                task_id,
            ),
        )
        self.conn.commit()

    def counts_for_month(self, year: int, month: int):
        rows = self.conn.execute(
            """
            SELECT due_date,
                   SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed
            FROM tasks
            WHERE due_date >= ? AND due_date < ?
            GROUP BY due_date
            """,
            (
                date(year, month, 1).isoformat(),
                (
                    date(year + 1, 1, 1)
                    if month == 12
                    else date(year, month + 1, 1)
                ).isoformat(),
            ),
        ).fetchall()
        return {r["due_date"]: (r["pending"], r["completed"]) for r in rows}

    def stats(self):
        today = date.today().isoformat()
        pending = self.conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE due_date = ? AND completed = 0",
            (today,),
        ).fetchone()["n"]
        completed_today = self.conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE due_date = ? AND completed = 1",
            (today,),
        ).fetchone()["n"]
        return pending, completed_today


class CalendarWidget(Static):
    def __init__(self, app: "KakarotTodo"):
        super().__init__()
        self.todo_app = app

    def render(self) -> Text:
        app = self.todo_app
        y, m = app.calendar_month.year, app.calendar_month.month
        data = app.db.counts_for_month(y, m)
        weeks = calendar.monthcalendar(y, m)

        out = Text()
        title = calendar.month_name[m] + f" {y}"
        out.append(title.center(28) + "\n", style="bold")
        out.append("Mo Tu We Th Fr Sa Su\n", style="dim")

        for week in weeks:
            for day in week:
                if day == 0:
                    out.append("   ")
                    continue

                d = date(y, m, day)
                key = d.isoformat()
                pending, done = data.get(key, (0, 0))
                selected = d == app.selected_date
                today = d == date.today()

                label = f"{day:2d}"
                if selected:
                    out.append(f"[{label}]", style="bold reverse")
                elif today:
                    out.append(f"{label}", style="bold underline")
                elif pending:
                    out.append(f"{label}", style="bold")
                else:
                    out.append(label)

                out.append(" ")
            out.append("\n")

        out.append("\n")
        out.append("● ", style="bold")
        out.append("tasks due  ")
        out.append("✓ ", style="bold")
        out.append("completed  ")
        out.append("[] ", style="reverse")
        out.append("selected")
        return out


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
        header.update(
            f"{self.selected_date.strftime('%A, %d %B %Y')}\n"
            f"Today-first task list"
        )

        task_list = self.query_one("#task_list", VerticalScroll)
        task_list.remove_children()

        if not tasks:
            task_list.mount(Static("No tasks for this date.\nPress 'a' to add one.", classes="task_row"))
        else:
            for i, task in enumerate(tasks):
                prefix = "✓" if task["completed"] else "☐"
                recur = "  🔁 daily" if task["recurring_id"] else ""
                text = f"{prefix}  {task['title']}{recur}"
                classes = "task_row"
                if task["completed"]:
                    classes += " completed"
                if i == self.selected_task_index:
                    classes += " selected_task"
                task_list.mount(Static(text, classes=classes))

        pending, completed = self.db.stats()
        status = self.query_one("#status", Static)
        status.update(
            f"Today: {completed} completed  •  {pending} pending   "
            f" |  ←→ date  ↑↓ task  Space complete  a add"
        )
        self.query_one(CalendarWidget).refresh()

    def current_tasks(self):
        return self.db.tasks_for(self.selected_date)

    def action_prev_task(self) -> None:
        tasks = self.current_tasks()
        if tasks:
            self.selected_task_index = max(0, self.selected_task_index - 1)
            self.refresh_view()

    def action_next_task(self) -> None:
        tasks = self.current_tasks()
        if tasks:
            self.selected_task_index = min(
                len(tasks) - 1, self.selected_task_index + 1
            )
            self.refresh_view()

    def action_toggle_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return
        task = tasks[self.selected_task_index]
        self.db.toggle(task["id"])
        self.refresh_view()

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

    def action_add_task(self) -> None:
        inp = self.query_one("#add_input", Input)
        inp.display = True
        inp.focus()

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

    def action_delete_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return
        task = tasks[self.selected_task_index]
        self.db.conn.execute("DELETE FROM tasks WHERE id = ?", (task["id"],))
        self.db.conn.commit()
        self.selected_task_index = max(0, self.selected_task_index - 1)
        self.refresh_view()


if __name__ == "__main__":
    KakarotTodo().run()
