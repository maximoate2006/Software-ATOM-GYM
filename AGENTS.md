# ATOM GYM

Single-file Python desktop app (tkinter + SQLite3) for gym member management. All UI strings, identifiers, and code comments are in **Spanish**.

## Run

```bash
python Gym.py
```

Windows-only: `import winsound` at the module top fails on any non-Windows OS.

## Build

```bash
pyinstaller Gym.spec
```

Produces `dist/gym.exe` (single-file, no console — note the lowercase name, set by `name='gym'` in the spec). Build artifacts live in `build/` and `dist/`. Built with Python 3.14. There is no requirements file; install Pillow if missing: `pip install Pillow`.

## Data vs. resources (important split)

- **Writable data** resolves next to the executable, not the source file. `BASE_DIR` (Gym.py:21) is `sys.executable`'s dir when frozen, else `Gym.py`'s dir. `gimnasio.db` and `clientes/` live there — i.e. inside `dist/` for the built exe. When running the exe, never edit the source tree expecting changes.
- **Read-only bundled assets** (`firma.ico`, `fondo.png`) load via `recurso()` (Gym.py:11), which uses PyInstaller's `sys._MEIPASS` temp dir and falls back to CWD in dev. Bundled via `datas=` in Gym.spec.

## Architecture

- **Entry point**: `__main__` block at `Gym.py:1735` → `inicializar_bd()`, `reparar_pagos_faltantes()`, then the `AtomGym` Tk app (fullscreen).
- **Database**: `gimnasio.db`, tables `clientes`, `pagos`, `admin`, `actividades`, `ingresos`, `cliente_actividad`. Schema created/migrated inline in `inicializar_bd()` (Gym.py:52). `monto_pago` added via `ALTER TABLE` inside a `try/except sqlite3.OperationalError` (Gym.py:135) — keep that ignore-on-exists pattern for future column additions.
- **DB access**: always use the `db_conn()` context manager (Gym.py:31); it sets `PRAGMA foreign_keys = ON`. Never open raw connections.
- **Seeded data**: `admin`/`admin123` and 5 default activities (Spinning, Yoga, Pesas, Funcional, Zumba) are inserted only if the tables are empty.
- **Client files**: attendance logs at `clientes/<Nombre>_<Apellido>_<DNI>/asistencias.txt`; the `<Nombre>_<Apellido>_<DNI>` folder name is derived from client fields at runtime.

## Gotchas

- `limpieza_automatica()` (Gym.py:1088, called from `AtomGym.__init__` Gym.py:188) deletes clients whose `vencimiento` is more than 90 days in the past on every startup, cascading to `pagos` and `cliente_actividad`. Test data older than 90 days will vanish.
- `reparar_pagos_faltantes()` (Gym.py:144, called at startup) back-fills a `pagos` row for clients with no payments.
- Dates are stored as `TEXT` in `YYYY-MM-DD` (SQLite date string compares work because of this). `estado_cliente()` (Gym.py:815) marks a client VENCIDOS / POR_VENCER (≤3 days) / AL_DIA.
- The 10-beep `winsound.Beep` alert runs in a `threading.Thread(daemon=True)` (Gym.py:1733) to avoid blocking the Tk event loop.
- `print()` calls (e.g. in `reparar_pagos_faltantes` and `limpieza_automatica`) are invisible in the console-less exe build — don't rely on them for debugging the frozen app.
