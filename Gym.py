import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import os
import sys
from PIL import Image, ImageTk
import winsound   
import threading 

def recurso(ruta):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, ruta)

# ======================================================
# CONFIG
# ======================================================
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)

CARPETA_CLIENTES = os.path.join(BASE_DIR, "clientes")

DB_NAME = os.path.join(BASE_DIR, "gimnasio.db")


from contextlib import contextmanager

@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


COLOR_BG = "#050505"
COLOR_PANEL = "#0D0D0D"
COLOR_BORDER = "#1A1A1A"
COLOR_RED = "#E60000"
COLOR_GREEN = "#00FF41"
COLOR_YELLOW = "#FFD700"
COLOR_WHITE = "#FFFFFF"
COLOR_SUB = "#888888"

# ======================================================
# BASE DE DATOS
# ======================================================
def inicializar_bd():

    if not os.path.exists(CARPETA_CLIENTES):
        os.makedirs(CARPETA_CLIENTES)
    with db_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            apellido TEXT,
            dni TEXT,
            descripcion TEXT,
            ultimo_pago TEXT,
            vencimiento TEXT,
            dias_semana TEXT,
            turno TEXT,
            modo_pago TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pagos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            fecha TEXT,
            monto REAL,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS admin(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            contrasena TEXT
        )
        """)

        cur.execute("SELECT COUNT(*) FROM admin")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO admin(usuario, contrasena) VALUES (?,?)",
                ("admin", "admin123")
            )

        cur.execute("""
        CREATE TABLE IF NOT EXISTS actividades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            descripcion TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ingresos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT,
            fecha TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS cliente_actividad(
            cliente_id INTEGER,
            actividad_id INTEGER,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
            FOREIGN KEY(actividad_id) REFERENCES actividades(id) ON DELETE CASCADE,
            PRIMARY KEY(cliente_id, actividad_id)
        )
        """)

        cur.execute("SELECT COUNT(*) FROM actividades")
        if cur.fetchone()[0] == 0:
            actividades_defecto = [
                ("Spinning", "Clase de ciclismo indoor"),
                ("Yoga", "Yoga relajante"),
                ("Pesas", "Entrenamiento con pesas"),
                ("Funcional", "Entrenamiento funcional"),
                ("Zumba", "Baile y cardio")
            ]
            cur.executemany("INSERT INTO actividades (nombre, descripcion) VALUES (?, ?)", actividades_defecto)

        conn.commit()
        try:
            cur.execute("ALTER TABLE clientes ADD COLUMN monto_pago REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pagos_fecha ON pagos(fecha)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pagos_cliente ON pagos(cliente_id)")
        conn.commit()

def reparar_pagos_faltantes():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.ultimo_pago, c.monto_pago
            FROM clientes c
            WHERE NOT EXISTS (SELECT 1 FROM pagos p WHERE p.cliente_id = c.id)
        """)
        sin_pagos = cur.fetchall()
        for cliente_id, ultimo_pago, monto in sin_pagos:
            fecha_pago = ultimo_pago if ultimo_pago else datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO pagos (cliente_id, fecha, monto) VALUES (?, ?, ?)",
                (cliente_id, fecha_pago, monto if monto is not None else 0))
        conn.commit()
        print(f"Se agregaron {len(sin_pagos)} pagos iniciales faltantes.")


# ======================================================
# APP
# ======================================================
class AtomGym:

    def __init__(self, root):
        self.root = root
        self.root.title("ATOMGYM")
        try:
            self.root.iconbitmap(recurso("firma.ico"))
        except Exception:
            pass

        self.root.attributes("-fullscreen", True)
        ancho = self.root.winfo_screenwidth()
        alto = self.root.winfo_screenheight()
        self.root.geometry(f"{ancho}x{alto}+0+0")

        self.root.configure(bg=COLOR_BG)

        self.main = tk.Frame(root, bg=COLOR_BG)
        self.main.pack(fill="both", expand=True)

        self.filtro_estado = "TODOS"

        self.estilos()
        self.inicio()
        self.limpieza_automatica()

    # --------------------------------------------------
    def estilos(self):
        style = ttk.Style()
        style.theme_use("default")

        style.configure(
            "Treeview",
            background="#0A0A0A",
            foreground="white",
            fieldbackground="#0A0A0A",
            rowheight=28,
            borderwidth=0
        )

        style.configure(
            "Treeview.Heading",
            background=COLOR_RED,
            foreground="white",
            font=("Arial Black", 11)
        )

    # --------------------------------------------------
    def limpiar(self):
        for w in self.main.winfo_children():
            w.destroy()

    # --------------------------------------------------
    def _make_scrollable(self, parent):
        canvas = tk.Canvas(parent, bg=COLOR_BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview, width=0)
        frame = tk.Frame(canvas, bg=COLOR_BG)

        canvas.create_window((0, 0), window=frame, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _update_inner_width(event):
            w = event.width
            canvas.itemconfig("inner", width=w)

        canvas.bind("<Configure>", _update_inner_width)
        frame.bind("<Configure>", _update_scrollregion)

        def _on_enter(event):
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        def _on_leave(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def _deferred_update():
            frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        parent.after(10, _deferred_update)

        return frame

    # --------------------------------------------------
    #Estadisticas financieras
    # --------------------------------------------------
    def obtener_estadisticas_financieras(self):
        with db_conn() as conn:
            cur = conn.cursor()

            hoy = datetime.now().strftime("%Y-%m-%d")
            mes_actual = datetime.now().strftime("%Y-%m")
            anio_actual = datetime.now().strftime("%Y")

            cur.execute("SELECT SUM(monto) FROM pagos WHERE fecha=?", (hoy,))
            monto_hoy = cur.fetchone()[0] or 0

            cur.execute("SELECT SUM(monto) FROM pagos WHERE fecha LIKE ?", (f"{mes_actual}%",))
            monto_mes = cur.fetchone()[0] or 0

            cur.execute("SELECT SUM(monto) FROM pagos WHERE fecha LIKE ?", (f"{anio_actual}%",))
            monto_anio = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(*) FROM pagos WHERE fecha LIKE ?", (f"{mes_actual}%",))
            nuevos_mes = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM pagos WHERE fecha LIKE ?", (f"{anio_actual}%",))
            nuevos_anio = cur.fetchone()[0]

            cur.execute("""
            SELECT COUNT(DISTINCT cliente_id)
            FROM pagos p
            WHERE p.fecha = (
                SELECT MIN(fecha)
                FROM pagos p2
                WHERE p2.cliente_id = p.cliente_id
            )
            AND p.fecha LIKE ?
            """, (f"{mes_actual}%",))
            clientes_nuevos = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(DISTINCT p1.cliente_id)
                FROM pagos p1
                WHERE p1.fecha LIKE ?
                    AND EXISTS (
                        SELECT 1
                        FROM pagos p2
                        WHERE p2.cliente_id = p1.cliente_id
                            AND p2.fecha < p1.fecha
                    )
            """, (f"{mes_actual}%",))
            clientes_renovados = cur.fetchone()[0]

        return monto_hoy, monto_anio, nuevos_mes, monto_mes, nuevos_anio, clientes_nuevos, clientes_renovados

    def abrir_panel_estadisticas(self):
        monto_hoy, monto_anio, nuevos_mes, monto_mes, nuevos_anio, clientes_nuevos, clientes_renovados = self.obtener_estadisticas_financieras()
        win = tk.Toplevel(self.root)
        self.ventana_estadisticas = win   
        win.title("Estadísticas Financieras")
        win.geometry("350x400")
        win.configure(bg=COLOR_PANEL)

        contenido = self._make_scrollable(win)

        datos = [
            ("Ingresos Hoy ($)", f"${monto_hoy:,.2f}"),
            ("Ingresos del Mes ($)", f"${monto_mes:,.2f}"),
            ("Ingresos Año ($)", f"${monto_anio:,.2f}"),
            ("Clientes Nuevos (Mes)", clientes_nuevos),
            ("Clientes Renovados (Mes)", clientes_renovados),
            ("Pagos Registrados (Año)", nuevos_anio),
        ]

        for titulo, valor in datos:
            frame = tk.Frame(contenido, bg=COLOR_BG, pady=10, padx=10)
            frame.pack(fill="x", padx=20, pady=5)
            tk.Label(frame, text=titulo, fg=COLOR_SUB, bg=COLOR_BG).pack(anchor="w")
            tk.Label(frame, text=valor, fg=COLOR_WHITE, font=("Arial", 14, "bold"), bg=COLOR_BG).pack(anchor="e")
    # ==================================================
    # PANTALLA INICIO
    # ==================================================
    def inicio(self):
        self.limpiar()

        self.bg_img = None
        self.logo_img = None

        try:
            img = Image.open(recurso("fondo.png"))
            img = img.resize(
                (
                    self.root.winfo_screenwidth(),
                    self.root.winfo_screenheight()
                )
            )
            self.bg_img = ImageTk.PhotoImage(img)
            fondo = tk.Label(self.main, image=self.bg_img)
            fondo.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception:
            pass

        try:
            logo = Image.open(recurso("firma.ico"))
            logo = logo.resize((120, 60))
            self.logo_img = ImageTk.PhotoImage(logo)
            firma = tk.Label(self.main, image=self.logo_img, bg="black", bd=0)
            firma.place(x=10, y=10)
            firma.lift()
        except Exception:
            pass

        # Entrada DNI
        self.ent_dni = tk.Entry(
            self.main,
            font=("Arial Black", 28),
            justify="center",
            bg="black",
            fg="white",
            insertbackground="white",
            bd=0,
            width=18
        )
        self.ent_dni.place(relx=0.5, rely=0.52, anchor="center", height=55)

        self.ent_dni.focus()
        self.ent_dni.bind("<Return>", lambda e: self.consultar_dni())

        # Botón cerrar
        tk.Button(
            self.main,
            text="✕",
            font=("Arial Black", 14),
            bg="#aa0000",
            fg="white",
            bd=0,
            command=self.root.destroy
        ).place(relx=0.97, rely=0.02, anchor="ne")

    
        tk.Button(
            self.main,
            text="─",
            font=("Arial Black", 14),
            bg="#222222",
            fg="white",
            bd=0,
            command=self.root.iconify 
        ).place(relx=0.945, rely=0.02, anchor="ne")

        # Botón Admin (ícono)
        tk.Button(
            self.main,
            text="⚙️",
            font=("Arial", 20),
            bg="#111111",
            fg="white",
            bd=0,
            command=self.login_admin,
            width=3
        ).place(relx=0.92, rely=0.02, anchor="ne")

    # --------------------------------------------------
    def actualizar_reloj(self):
        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]

        ahora = datetime.now()
        hora = ahora.strftime("%H:%M:%S")
        dia = dias[ahora.weekday()]
        fecha = ahora.strftime("%d/%m/%Y")

        if hasattr(self, "lbl_hora"):
            self.lbl_hora.config(text=hora)

        if hasattr(self, "lbl_fecha"):
            self.lbl_fecha.config(text=f"{dia} - {fecha}")

        self.root.after(1000, self.actualizar_reloj)

    # ==================================================
    # CONSULTA DNI
    # ==================================================
    def consultar_dni(self):
        dni = self.ent_dni.get().strip()
        
        if not dni:
            return

        try:
            with db_conn() as conn:
                cur = conn.cursor() 
                
                cur.execute("""
                    SELECT id, nombre, apellido, dias_semana, turno, vencimiento
                    FROM clientes
                    WHERE dni=?
                """, (dni,))

                dato = cur.fetchone()
                
                if not dato:
                    self.popup_mensaje(
                        "DNI NO ENCONTRADO",
                        "EL SOCIO NO EXISTE EN LA BASE DE DATOS",
                        COLOR_RED
                    )
                    return

                id_cliente, nombre, apellido, dias_semana_raw, turno, vencimiento = dato

                estado = self.estado_cliente(vencimiento)
                ahora = datetime.now()

                nombre_carpeta = f"{nombre}_{apellido}_{dni}"
                ruta_cliente = os.path.join(CARPETA_CLIENTES, nombre_carpeta)
                if not os.path.exists(ruta_cliente):
                    os.makedirs(ruta_cliente)
                ruta_archivo = os.path.join(ruta_cliente, "asistencias.txt")
                fecha_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")

                if estado == "VENCIDOS":
                    with open(ruta_archivo, "a", encoding="utf-8") as archivo:
                        archivo.write(f"{fecha_actual} vencido {vencimiento}\n")

                    self.reproducir_alerta() 
                    self.popup_mensaje(
                        f"ACCESO DENEGADO: {nombre.upper()} {apellido.upper()}",
                        f"CUOTA VENCIDA EL {vencimiento}\nPASE POR RECEPCIÓN",
                        COLOR_RED
                    )
                    return

                hoy_str = ahora.strftime("%Y-%m-%d")
                cur.execute("SELECT COUNT(*) FROM ingresos WHERE dni=? AND fecha LIKE ?", (dni, f"{hoy_str}%"))
                ya_ingreso_hoy = cur.fetchone()[0] > 0

                if not ya_ingreso_hoy:
                    cur.execute("""
                        INSERT INTO ingresos(dni, fecha)
                        VALUES (?, ?)
                    """, (dni, ahora.strftime("%Y-%m-%d %H:%M:%S")))
                    
                    with open(ruta_archivo, "a", encoding="utf-8") as archivo:
                        archivo.write(f"{fecha_actual} *\n")

                conn.commit()

                dias_cliente = dias_semana_raw.split(",") if dias_semana_raw else []
                
                cur.execute("""
                    SELECT a.nombre FROM actividades a
                    JOIN cliente_actividad ca ON a.id = ca.actividad_id
                    WHERE ca.cliente_id = ?
                """, (id_cliente,))
                actividades_cliente = [row[0] for row in cur.fetchall()]

                if estado == "POR_VENCER":
                    self.popup_mensaje(
                        f"AVISO: {nombre.upper()} {apellido.upper()}",
                        f"CUOTA PRÓXIMA A VENCER\nSU ABONO VENCE EL {vencimiento}",
                        COLOR_YELLOW
                    )

                dias_hoy = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                dia_actual = dias_hoy[ahora.weekday()]
                hora_actual = ahora.hour

                coincide_dia = dia_actual in dias_cliente
                coincide_hora = False

                if turno == "Mañana":
                    coincide_hora = 6 <= hora_actual < 12
                elif turno == "Tarde":
                    coincide_hora = 12 <= hora_actual < 18
                elif turno == "Noche":
                    coincide_hora = 18 <= hora_actual < 23
                elif turno == "Libre":
                    coincide_hora = True

                if not coincide_dia:
                    self.popup_mensaje(
                        "NO ES SU DÍA DE ENTRENAMIENTO",
                        f"DÍAS DE ENTRENAMIENTO:\n{', '.join(dias_cliente)}",
                        COLOR_RED
                    )
                elif not coincide_hora:
                    self.popup_mensaje(
                        "FUERA DE HORARIO",
                        f"SU ENTRENAMIENTO ES EN EL TURNO:\n{turno}",
                        COLOR_RED
                    )
                else:
                    texto_act = f"\nActividades: {', '.join(actividades_cliente)}" if actividades_cliente else ""
                    self.popup_mensaje(
                        f"BIENVENIDO {nombre.upper()} {apellido.upper()}",
                        f"VENCIMIENTO: {vencimiento}\n{texto_act}\n¡QUE TENGA UN BUEN ENTRENAMIENTO!",
                        COLOR_GREEN
                    )
        except Exception as e:
            self.popup_mensaje(
                "ERROR",
                f"OCURRIÓ UN ERROR AL CONSULTAR:\n{str(e)}",
                COLOR_RED
            )

        self.ent_dni.delete(0, "end")

    # --------------------------------------------------
    def popup_mensaje(self, t1, t2, color):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=color)

        ancho = 900
        alto = 360

        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)

        win.geometry(f"{ancho}x{alto}+{x}+{y}")

        tk.Label(
            win,
            text=t1,
            font=("Impact", 34, "bold"),
            fg="Black",
            bg=color
        ).pack(pady=(90, 20))

        tk.Label(
            win,
            text=t2,
            font=("Impact", 22),
            fg="Black",
            bg=color
        ).pack()

        win.after(6500, win.destroy)

    # ==================================================
    # LOGIN
    # ==================================================
    def login_admin(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=COLOR_BG)

        ancho = 500
        alto = 350

        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)

        win.geometry(f"{ancho}x{alto}+{x}+{y}")

        tk.Label(
            win,
            text="PANEL ADMIN",
            font=("Arial Black", 22),
            fg="white",
            bg=COLOR_BG
        ).pack(pady=20)

        user = tk.Entry(win, font=("Arial", 16), justify="center")
        user.pack(pady=10)

        pas = tk.Entry(win, font=("Arial", 16), justify="center", show="*")
        pas.pack(pady=10)

        def entrar():
            with db_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM admin WHERE usuario=? AND contrasena=?",
                    (user.get(), pas.get())
                )
                ok = cur.fetchone()

            if ok:
                win.destroy()
                self.dashboard()
            else:
                messagebox.showerror("Error", "Datos incorrectos")

        tk.Button(
            win,
            text="INGRESAR",
            font=("Arial Black", 12),
            bg=COLOR_RED,
            fg="white",
            width=18,
            command=entrar
        ).pack(pady=15)

        tk.Button(
            win,
            text="CERRAR",
            font=("Arial Black", 11),
            bg="#222",
            fg="white",
            width=18,
            command=win.destroy
        ).pack()

    # ==================================================
    # PANEL ADMIN
    # ==================================================
    def dashboard(self):
        self.limpiar()

        tk.Label(
            self.main,
            text="PANEL ADMINISTRADOR",
            font=("Arial Black", 28),
            fg="white",
            bg=COLOR_BG
        ).pack(pady=10)

        tk.Button(
            self.main,
            text="SALIR",
            bg=COLOR_RED,
            fg="white",
            command=self.inicio
        ).place(x=20, y=20)

        total, al_dia, por_vencer, vencidos, ingresos_hoy = self.estadisticas()

        
        fila_container = tk.Frame(self.main, bg=COLOR_BG)
        fila_container.pack(pady=10, fill="x")

        
        fila = tk.Frame(fila_container, bg=COLOR_BG)
        fila.pack(anchor="center")

        self.card(fila, "TOTAL", total, "white", "TODOS")
        self.card(fila, "AL DÍA", al_dia, COLOR_GREEN, "AL_DIA")
        self.card(fila, "POR VENCER", por_vencer, COLOR_YELLOW, "POR_VENCER")
        self.card(fila, "VENCIDOS", vencidos, COLOR_RED, "VENCIDOS")
        self.card(fila, "INGRESOS HOY", ingresos_hoy, "#00BFFF", "INGRESOS_HOY")

        busc = tk.Frame(self.main, bg=COLOR_BG)
        busc.pack(pady=10)

        btn_est = tk.Button(fila, text="ESTADÍSTICAS", command=self.abrir_panel_estadisticas, 
                            bg=COLOR_PANEL, fg=COLOR_WHITE, font=("Arial", 10, "bold"), 
                            width=15, height=3)
        btn_est.pack(side="left", padx=5)

        tk.Label(
            busc,
            text="BUSCAR:",
            font=("Arial Black", 12),
            fg="white",
            bg=COLOR_BG
        ).pack(side="left", padx=8)

        self.buscar_var = tk.StringVar()
        self.buscar_var.trace_add("write", lambda *args: self.cargar_tabla())

        tk.Entry(
            busc,
            textvariable=self.buscar_var,
            font=("Arial", 14),
            width=25
        ).pack(side="left")

        tk.Button(
            busc,
            text="+ NUEVO CLIENTE",
            bg=COLOR_GREEN,
            fg="black",
            command=self.form_cliente
        ).pack(side="left", padx=10)

        tk.Button(
            busc,
            text="EDITAR CLIENTE",
            bg=COLOR_YELLOW,
            fg="black",
            command=self.editar_cliente
        ).pack(side="left", padx=10)

        tk.Button(
            busc,
            text="RENOVAR CLIENTE",
            bg="#00BFFF",
            fg="black",
            command=self.renovar_cliente
        ).pack(side="left", padx=10)

        tk.Button(
            busc,
            text="ELIMINAR CLIENTE",
            bg=COLOR_RED,
            fg="white",
            command=self.eliminar_cliente
        ).pack(side="left", padx=10)

        tk.Button(
            busc,
            text="ACTIVIDADES",
            bg="#FFA500",
            fg="black",
            command=self.gestion_actividades
        ).pack(side="left", padx=10)

        frame = tk.Frame(self.main, bg=COLOR_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=15)

        columnas = (("ID", "Nombre", "DNI", "Actividades","Ingresos","Vencimiento", "Turno", "Modo Pago"))

        self.tree = ttk.Treeview(
            frame,
            columns=columnas,
            show="headings"
        )

        for c in columnas:
            self.tree.heading(c, text=c)

            if c == "Actividades":
                self.tree.column(c, anchor="center", width=350)
            else:
                self.tree.column(c, anchor="center", width=150)

        self.tree.pack(fill="both", expand=True)

        self.cargar_tabla()

    # --------------------------------------------------
    def card(self, parent, titulo, valor, color, filtro):
        f = tk.Frame(parent, bg="#111", padx=20, pady=10, cursor="hand2")
        f.pack(side="left", padx=8)

        tk.Label(
            f,
            text=titulo,
            font=("Arial Black", 10),
            fg="white",
            bg="#111"
        ).pack()

        tk.Label(
            f,
            text=str(valor),
            font=("Arial Black", 22),
            fg=color,
            bg="#111"
        ).pack()

        f.bind("<Button-1>", lambda e: self.aplicar_filtro(filtro))
        for w in f.winfo_children():
            w.bind("<Button-1>", lambda e: self.aplicar_filtro(filtro))

    # --------------------------------------------------
    def aplicar_filtro(self, filtro):
        self.filtro_estado = filtro
        self.cargar_tabla()

    # --------------------------------------------------
    def estado_cliente(self, vencimiento):
        try:
            hoy = datetime.now().date()
            fecha = datetime.strptime(vencimiento, "%Y-%m-%d").date()
            dias = (fecha - hoy).days

            if dias < 0:
                return "VENCIDOS"
            elif dias <= 3:
                return "POR_VENCER"
            else:
                return "AL_DIA"
        except Exception:
            return "AL_DIA"
    #---------------------------------------------------
    def dias_pago(self, modo):
        if modo == "Mensual":
            return 30
        elif modo == "Quincenal":
            return 15
        elif modo == "Semanal":
            return 7
        return 30

    # --------------------------------------------------
    def estadisticas(self):
        with db_conn() as conn:
            cur = conn.cursor()

            cur.execute("SELECT vencimiento FROM clientes")
            filas = cur.fetchall()

            hoy_str = datetime.now().strftime("%Y-%m-%d")
            cur.execute("SELECT COUNT(*) FROM ingresos WHERE fecha LIKE ?", (f"{hoy_str}%",))
            ingresos_hoy = cur.fetchone()[0]

        total = len(filas)
        al_dia = 0
        por_vencer = 0
        vencidos = 0

        for f in filas:
            estado = self.estado_cliente(f[0])

            if estado == "AL_DIA":
                al_dia += 1
            elif estado == "POR_VENCER":
                por_vencer += 1
            elif estado == "VENCIDOS":
                vencidos += 1

        
        return total, al_dia, por_vencer, vencidos, ingresos_hoy

    # --------------------------------------------------
    def cargar_tabla(self):

        for row in self.tree.get_children():
            self.tree.delete(row)

        texto = self.buscar_var.get().strip()

        with db_conn() as conn:
            cur = conn.cursor()

            query =""" 
               SELECT 
                c.id,
                c.nombre || ' ' || c.apellido,
                c.dni,
                IFNULL(
                    GROUP_CONCAT(DISTINCT a.nombre),
                    'Sin actividades'
                ) as actividades,
                COUNT(DISTINCT i.id) as ingresos,
                c.vencimiento,
                c.turno,
                c.modo_pago
            FROM clientes c
            LEFT JOIN cliente_actividad ca
                ON c.id = ca.cliente_id
            LEFT JOIN actividades a
                ON ca.actividad_id = a.id
            LEFT JOIN ingresos i
                ON c.dni = i.dni
            """

            parametros = []

            if self.filtro_estado == "INGRESOS_HOY":
                hoy_str = datetime.now().strftime("%Y-%m-%d")
                query += " WHERE c.dni IN (SELECT dni FROM ingresos WHERE fecha LIKE ?)"
                parametros.append(f"{hoy_str}%")

            query += " GROUP BY c.id ORDER BY c.nombre"

            cur.execute(query, tuple(parametros))
            filas = cur.fetchall()

        for fila in filas:
            estado = self.estado_cliente(fila[5])

            # Excluimos "TODOS" e "INGRESOS_HOY" del filtro de estados por vencimiento
            if self.filtro_estado not in ["TODOS", "INGRESOS_HOY"]:
                if estado != self.filtro_estado:
                    continue

            if texto:
                combinado = f"{fila[1]} {fila[2]}"
                if texto.lower() not in combinado.lower():
                    continue

            self.tree.insert("", "end", values=fila)
    # ==================================================
    # GESTIÓN DE ACTIVIDADES
    # ==================================================
    def gestion_actividades(self):
        win = tk.Toplevel(self.root)
        win.title("Gestionar Actividades")
        win.geometry("600x500")
        win.configure(bg=COLOR_BG)

        frame_lista = tk.Frame(win, bg=COLOR_BG)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(frame_lista, columns=("ID", "Nombre", "Descripción"), show="headings")
        tree.heading("ID", text="ID")
        tree.heading("Nombre", text="Nombre")
        tree.heading("Descripción", text="Descripción")
        tree.column("ID", width=50)
        tree.column("Nombre", width=150)
        tree.column("Descripción", width=350)
        tree.pack(fill="both", expand=True)

        def cargar_actividades():
            for row in tree.get_children():
                tree.delete(row)
            with db_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, nombre, descripcion FROM actividades ORDER BY nombre")
                for row in cur.fetchall():
                    tree.insert("", "end", values=row)

        def agregar():
            dialog = tk.Toplevel(win)
            dialog.title("Nueva Actividad")
            dialog.geometry("400x200")
            dialog.configure(bg=COLOR_BG)
            tk.Label(dialog, text="Nombre:", bg=COLOR_BG, fg="white").pack(pady=5)
            nombre_ent = tk.Entry(dialog, width=30)
            nombre_ent.pack()
            tk.Label(dialog, text="Descripción:", bg=COLOR_BG, fg="white").pack(pady=5)
            desc_ent = tk.Entry(dialog, width=30)
            desc_ent.pack()
            def guardar():
                nombre = nombre_ent.get().strip()
                desc = desc_ent.get().strip()
                if nombre:
                    with db_conn() as conn:
                        cur = conn.cursor()
                        try:
                            cur.execute("INSERT INTO actividades (nombre, descripcion) VALUES (?,?)", (nombre, desc))
                            conn.commit()
                        except sqlite3.IntegrityError:
                            messagebox.showerror("Error", "Ya existe una actividad con ese nombre")
                    dialog.destroy()
                    cargar_actividades()
            tk.Button(dialog, text="Guardar", command=guardar, bg=COLOR_GREEN).pack(pady=10)

        def editar():
            selec = tree.selection()
            if not selec:
                messagebox.showwarning("Aviso", "Seleccione una actividad")
                return
            item = tree.item(selec[0])
            id_act = item["values"][0]
            nombre_act = item["values"][1]
            desc_act = item["values"][2]
            dialog = tk.Toplevel(win)
            dialog.title("Editar Actividad")
            dialog.geometry("400x200")
            dialog.configure(bg=COLOR_BG)
            tk.Label(dialog, text="Nombre:", bg=COLOR_BG, fg="white").pack(pady=5)
            nombre_ent = tk.Entry(dialog, width=30)
            nombre_ent.insert(0, nombre_act)
            nombre_ent.pack()
            tk.Label(dialog, text="Descripción:", bg=COLOR_BG, fg="white").pack(pady=5)
            desc_ent = tk.Entry(dialog, width=30)
            desc_ent.insert(0, desc_act)
            desc_ent.pack()
            def guardar():
                nombre = nombre_ent.get().strip()
                desc = desc_ent.get().strip()
                if nombre:
                    with db_conn() as conn:
                        cur = conn.cursor()
                        try:
                            cur.execute("UPDATE actividades SET nombre=?, descripcion=? WHERE id=?", (nombre, desc, id_act))
                            conn.commit()
                        except sqlite3.IntegrityError:
                            messagebox.showerror("Error", "Ya existe otra actividad con ese nombre")
                    dialog.destroy()
                    cargar_actividades()
            tk.Button(dialog, text="Guardar", command=guardar, bg=COLOR_GREEN).pack(pady=10)

        def eliminar():
            selec = tree.selection()
            if not selec:
                messagebox.showwarning("Aviso", "Seleccione una actividad")
                return
            item = tree.item(selec[0])
            id_act = item["values"][0]
            if messagebox.askyesno("Confirmar", "¿Eliminar esta actividad? Se quitará de todos los clientes que la tengan."):
                with db_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM actividades WHERE id=?", (id_act,))
                    conn.commit()
                cargar_actividades()

        btn_frame = tk.Frame(win, bg=COLOR_BG)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Agregar", command=agregar, bg=COLOR_GREEN, fg="black").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Editar", command=editar, bg=COLOR_YELLOW, fg="black").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Eliminar", command=eliminar, bg=COLOR_RED, fg="white").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cerrar", command=win.destroy, bg="gray", fg="white").pack(side="left", padx=5)

        cargar_actividades()

    # ==================================================
    # ELIMINAR CLIENTE (MANUAL)
    # ==================================================
    def eliminar_cliente(self):
        seleccionado = self.tree.selection()
        if not seleccionado:
            messagebox.showwarning("Aviso", "Seleccione un cliente para eliminar")
            return
        
        item = self.tree.item(seleccionado[0])
        id_cliente = item["values"][0]
        nombre = item["values"][1]
        
        confirmar = messagebox.askyesno(
            "Confirmar", 
            f"¿Está seguro de eliminar permanentemente a {nombre}?"
        )
        
        if confirmar:
            try:
                with db_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT nombre, apellido, dni FROM clientes WHERE id=?", (id_cliente,))
                    datos_cliente = cur.fetchone()
                    cur.execute("DELETE FROM cliente_actividad WHERE cliente_id=?", (id_cliente,))
                    cur.execute("DELETE FROM pagos WHERE cliente_id=?", (id_cliente,))
                    cur.execute("DELETE FROM clientes WHERE id=?", (id_cliente,))
                    conn.commit()

                if datos_cliente:
                    try:
                        nombre_cliente_dir = f"{datos_cliente[0]}_{datos_cliente[1]}_{datos_cliente[2]}"
                        ruta_cliente = os.path.join(CARPETA_CLIENTES, nombre_cliente_dir)
                        if os.path.exists(ruta_cliente):
                            import shutil
                            shutil.rmtree(ruta_cliente, ignore_errors=True)
                    except Exception:
                        pass

                self.dashboard()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar:\n{str(e)}")
    # ==================================================
    # LIMPIEZA AUTOMÁTICA (REGISTROS OBSOLETOS)
    # ==================================================
    def limpieza_automatica(self):
        limite = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clientes WHERE vencimiento < ?", (limite,))
            ids_vencidos = [row[0] for row in cur.fetchall()]
            
            if ids_vencidos:
                placeholders = ",".join("?" * len(ids_vencidos))
                cur.execute(f"DELETE FROM cliente_actividad WHERE cliente_id IN ({placeholders})", ids_vencidos)
                cur.execute(f"DELETE FROM pagos WHERE cliente_id IN ({placeholders})", ids_vencidos)
                cur.execute(f"DELETE FROM clientes WHERE vencimiento < ?", (limite,))
                registros_borrados = cur.rowcount
                conn.commit()
            else:
                registros_borrados = 0
        
        if registros_borrados > 0:
            print(f"Limpieza: Se eliminaron {registros_borrados} registros antiguos.")
    # ==================================================
    # NUEVO CLIENTE
    # ==================================================
    def form_cliente(self):
        win = tk.Toplevel(self.root)
        win.title("Nuevo Cliente")
        win.geometry("500x950")
        win.configure(bg=COLOR_BG)

        contenido = self._make_scrollable(win)

        campos = {}

        labels = [
            "Nombre",
            "Apellido",
            "DNI",
            "Descripción",
            "Fecha Pago"
        ]

        for txt in labels:
            tk.Label(
                contenido,
                text=txt,
                fg="white",
                bg=COLOR_BG
            ).pack(anchor="w", padx=20, pady=(8, 2))

            ent = tk.Entry(contenido, width=35)
            ent.pack(padx=20)
            campos[txt] = ent

        campos["Fecha Pago"].insert(0, datetime.now().strftime("%Y-%m-%d"))

        # MODO PAGO
        tk.Label(contenido, text="Modo de Pago", fg="white", bg=COLOR_BG).pack(
            anchor="w", padx=20, pady=(10, 2)
        )
        tk.Label(contenido, text="Monto Pagado ($)", fg="white", bg=COLOR_BG).pack(anchor="w", padx=20, pady=(10, 2))
        ent_monto = tk.Entry(contenido, width=35)
        ent_monto.pack(padx=20)
        ent_monto.insert(0, "0")

        combo_pago = ttk.Combobox(
            contenido,
            values=["Mensual", "Quincenal", "Semanal"],
            state="readonly"
        )
        combo_pago.pack(padx=20)
        combo_pago.current(0)

        # TURNO
        tk.Label(contenido, text="Turno", fg="white", bg=COLOR_BG).pack(
            anchor="w", padx=20, pady=(10, 2)
        )

        combo = ttk.Combobox(
            contenido,
            values=["Mañana", "Tarde", "Noche", "Libre"],
            state="readonly"
        )
        combo.pack(padx=20)
        combo.current(0)

        # DIAS
        tk.Label(
            contenido,
            text="Días de asistencia",
            fg="white",
            bg=COLOR_BG
        ).pack(anchor="w", padx=20, pady=(10, 2))

        dias_nombres = [
            "Lunes", "Martes", "Miércoles",
            "Jueves", "Viernes", "Sábado"
        ]

        dias_vars = {}

        for dia in dias_nombres:
            var = tk.IntVar()
            dias_vars[dia] = var

            tk.Checkbutton(
                contenido,
                text=dia,
                variable=var,
                fg="white",
                bg=COLOR_BG,
                selectcolor="#111"
            ).pack(anchor="w", padx=30)

        # ACTIVIDADES
        tk.Label(
            contenido,
            text="Actividades",
            fg="white",
            bg=COLOR_BG
        ).pack(anchor="w", padx=20, pady=(10, 2))

        frame_act = tk.Frame(contenido, bg=COLOR_BG)
        frame_act.pack(fill="x", padx=30, pady=5)

        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, nombre FROM actividades ORDER BY nombre")
            actividades = cur.fetchall()

        actividades_vars = {}
        for act_id, act_nombre in actividades:
            var = tk.IntVar()
            chk = tk.Checkbutton(
                frame_act,
                text=act_nombre,
                variable=var,
                fg="white",
                bg=COLOR_BG,
                selectcolor="#111"
            )
            chk.pack(anchor="w")
            actividades_vars[act_id] = var

        def guardar():
            try:
                modo = combo_pago.get()
                fecha_pago = campos["Fecha Pago"].get()
                try:
                    monto_pago = float(ent_monto.get())
                except ValueError:
                    messagebox.showerror("Error", "El monto debe ser un número válido.")
                    return
                if not campos["Nombre"].get().strip():
                    messagebox.showerror(
                        "Error",
                        "Debe ingresar un nombre."
                    )
                    return

                if not campos["Apellido"].get().strip():
                    messagebox.showerror(
                        "Error",
                        "Debe ingresar un apellido."
                    )
                    return

                if not campos["DNI"].get().strip():
                    messagebox.showerror(
                        "Error",
                        "Debe ingresar un DNI."
                    )
                    return

                dni_limpio = campos["DNI"].get().strip().replace(".", "")
                with db_conn() as conn_check:
                    cur_check = conn_check.cursor()
                    cur_check.execute("SELECT COUNT(*) FROM clientes WHERE dni=?", (dni_limpio,))
                    if cur_check.fetchone()[0] > 0:
                        messagebox.showerror("Error", "Ya existe un cliente con ese DNI.")
                        return

                if monto_pago < 0:
                    messagebox.showerror(
                        "Error",
                        "El monto no puede ser negativo."
                    )
                    return

                base = datetime.strptime(fecha_pago, "%Y-%m-%d")
                venc = base + timedelta(days=self.dias_pago(modo))

                dias_texto = ",".join(
                    [d for d in dias_nombres if dias_vars[d].get() == 1]
                )
                if not dias_texto:
                    messagebox.showerror(
                        "Error",
                        "Debe seleccionar al menos un día."
                    )
                    return

                with db_conn() as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        INSERT INTO clientes(
                            nombre, apellido, dni, descripcion,
                            ultimo_pago, vencimiento,
                            dias_semana, turno, modo_pago, monto_pago
                        )
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                    """, (
                        campos["Nombre"].get(),
                        campos["Apellido"].get(),
                        campos["DNI"].get().strip().replace(".", ""),
                        campos["Descripción"].get(),
                        fecha_pago,
                        venc.strftime("%Y-%m-%d"),
                        dias_texto,
                        combo.get(),
                        modo,
                        monto_pago
                    ))

                    cliente_id = cur.lastrowid
                    cur.execute("""
                    INSERT INTO pagos(cliente_id, fecha, monto)
                    VALUES (?, ?, ?)
                """, (
                    cliente_id,
                    fecha_pago,
                    monto_pago
                ))

                    for act_id, var in actividades_vars.items():
                        if var.get() == 1:
                            cur.execute("INSERT INTO cliente_actividad (cliente_id, actividad_id) VALUES (?, ?)", (cliente_id, act_id))

                    nombre_cliente = f"{campos['Nombre'].get()}_{campos['Apellido'].get()}_{campos['DNI'].get()}"
                    ruta_cliente = os.path.join(CARPETA_CLIENTES, nombre_cliente)
                    if not os.path.exists(ruta_cliente):
                        os.makedirs(ruta_cliente)

                    conn.commit()

                win.destroy()
                self.root.after(100, self.dashboard)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el cliente:\n{str(e)}")

        tk.Button(
            contenido,
            text="GUARDAR",
            bg=COLOR_GREEN,
            fg="black",
            command=guardar
        ).pack(pady=25)

    # ==================================================
    # EDITAR CLIENTE
    # ==================================================
    def editar_cliente(self):
        seleccionado = self.tree.selection()

        if not seleccionado:
            messagebox.showwarning("Aviso", "Seleccione un cliente")
            return

        item = self.tree.item(seleccionado[0])
        id_cliente = item["values"][0]

        with db_conn() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT nombre, apellido, dni, descripcion,
                       ultimo_pago, dias_semana,
                       turno, modo_pago, monto_pago
                FROM clientes
                WHERE id=?
            """, (id_cliente,))

            datos = cur.fetchone()

            cur.execute("SELECT actividad_id FROM cliente_actividad WHERE cliente_id=?", (id_cliente,))
            act_asignadas = [row[0] for row in cur.fetchall()]

        win = tk.Toplevel(self.root)
        win.title("Editar Cliente")
        win.geometry("500x950")
        win.configure(bg=COLOR_BG)

        contenido = self._make_scrollable(win)

        campos = {}

        labels = [
            "Nombre",
            "Apellido",
            "DNI",
            "Descripción",
            "Fecha Pago"
        ]

        for i, txt in enumerate(labels):
            tk.Label(
                contenido,
                text=txt,
                fg="white",
                bg=COLOR_BG
            ).pack(anchor="w", padx=20, pady=(8, 2))

            ent = tk.Entry(contenido, width=35)
            ent.pack(padx=20)
            ent.insert(0, datos[i])

            campos[txt] = ent

        # MODO PAGO
        tk.Label(contenido, text="Modo de Pago", fg="white", bg=COLOR_BG).pack(
            anchor="w", padx=20, pady=(10, 2)
        )

        combo_pago = ttk.Combobox(
            contenido,
            values=["Mensual", "Quincenal", "Semanal"],
            state="readonly"
        )
        combo_pago.pack(padx=20)
        combo_pago.set(datos[7] if datos[7] else "Mensual")

        # MONTO PAGO
        tk.Label(contenido, text="Monto Pagado ($)", fg="white", bg=COLOR_BG).pack(
            anchor="w", padx=20, pady=(10, 2)
        )
        ent_monto = tk.Entry(contenido, width=35)
        ent_monto.pack(padx=20)
        ent_monto.insert(0, datos[8] if datos[8] is not None else 0)

        # TURNO
        tk.Label(contenido, text="Turno", fg="white", bg=COLOR_BG).pack(
            anchor="w", padx=20, pady=(10, 2)
        )

        combo = ttk.Combobox(
            contenido,
            values=["Mañana", "Tarde", "Noche", "Libre"],
            state="readonly"
        )
        combo.pack(padx=20)
        combo.set(datos[6])

        # DIAS
        tk.Label(
            contenido,
            text="Días de asistencia",
            fg="white",
            bg=COLOR_BG
        ).pack(anchor="w", padx=20, pady=(10, 2))

        dias_nombres = [
            "Lunes", "Martes", "Miércoles",
            "Jueves", "Viernes", "Sábado"
        ]

        actuales = datos[5].split(",") if datos[5] else []
        dias_vars = {}

        for dia in dias_nombres:
            var = tk.IntVar(value=1 if dia in actuales else 0)
            dias_vars[dia] = var

            tk.Checkbutton(
                contenido,
                text=dia,
                variable=var,
                fg="white",
                bg=COLOR_BG,
                selectcolor="#111"
            ).pack(anchor="w", padx=30)

        # ACTIVIDADES
        tk.Label(
            contenido,
            text="Actividades",
            fg="white",
            bg=COLOR_BG
        ).pack(anchor="w", padx=20, pady=(10, 2))

        frame_act = tk.Frame(contenido, bg=COLOR_BG)
        frame_act.pack(fill="x", padx=30, pady=5)

        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, nombre FROM actividades ORDER BY nombre")
            actividades = cur.fetchall()

        actividades_vars = {}
        for act_id, act_nombre in actividades:
            var = tk.IntVar(value=1 if act_id in act_asignadas else 0)
            chk = tk.Checkbutton(
                frame_act,
                text=act_nombre,
                variable=var,
                fg="white",
                bg=COLOR_BG,
                selectcolor="#111"
            )
            chk.pack(anchor="w")
            actividades_vars[act_id] = var

        def guardar():
            try:
                modo = combo_pago.get()
                fecha_pago = campos["Fecha Pago"].get()

                try:
                    monto_val = float(ent_monto.get())
                except ValueError:
                    messagebox.showerror("Error", "El monto debe ser un número válido.")
                    return

                base = datetime.strptime(fecha_pago, "%Y-%m-%d")
                venc = base + timedelta(days=self.dias_pago(modo))

                dias_texto = ",".join(
                    [d for d in dias_nombres if dias_vars[d].get() == 1]
                )

                with db_conn() as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        UPDATE clientes SET
                            nombre=?,
                            apellido=?,
                            dni=?,
                            descripcion=?,
                            ultimo_pago=?,
                            vencimiento=?,
                            dias_semana=?,
                            turno=?,
                            modo_pago=?,
                            monto_pago=?
                        WHERE id=?
                    """, (
                        campos["Nombre"].get(),
                        campos["Apellido"].get(),
                        campos["DNI"].get().strip().replace(".", ""),
                        campos["Descripción"].get(),
                        fecha_pago,
                        venc.strftime("%Y-%m-%d"),
                        dias_texto,
                        combo.get(),
                        modo,
                        monto_val,
                        id_cliente
                    ))

                    cur.execute("DELETE FROM cliente_actividad WHERE cliente_id=?", (id_cliente,))
                    for act_id, var in actividades_vars.items():
                        if var.get() == 1:
                            cur.execute("INSERT INTO cliente_actividad (cliente_id, actividad_id) VALUES (?, ?)", (id_cliente, act_id))

                    conn.commit()

                win.destroy()
                self.root.after(100, self.dashboard)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo editar el cliente:\n{str(e)}")

        tk.Button(
            contenido,
            text="GUARDAR CAMBIOS",
            bg=COLOR_GREEN,
            fg="black",
            command=guardar
        ).pack(pady=25)

    # ======================================================
    # RENOVAR CLIENTE
    # ======================================================
    def renovar_cliente(self):
        seleccionado = self.tree.selection()

        if not seleccionado:
            messagebox.showwarning("Aviso", "Seleccione un cliente")
            return

        item = self.tree.item(seleccionado[0])
        id_cliente = item["values"][0]
        nombre = item["values"][1]
        venc_actual = item["values"][5]

        win = tk.Toplevel(self.root)
        win.title("Renovar Cliente")
        win.geometry("420x320")
        win.configure(bg=COLOR_BG)

        contenido = self._make_scrollable(win)

        tk.Label(
            contenido,
            text="RENOVAR CLIENTE",
            font=("Arial Black", 18),
            fg="white",
            bg=COLOR_BG
        ).pack(pady=15)
        tk.Label(contenido, text="Monto de Renovación ($)", fg="white", bg=COLOR_BG).pack()
        ent_monto_renov = tk.Entry(contenido)
        ent_monto_renov.pack(pady=5)
        ent_monto_renov.insert(0, "0")
        tk.Label(
            contenido,
            text=nombre,
            fg="white",
            bg=COLOR_BG
        ).pack()

        tk.Label(
            contenido,
            text=f"Vence: {venc_actual}",
            fg="white",
            bg=COLOR_BG
        ).pack(pady=10)

        tk.Label(
            contenido,
            text="Plan",
            fg="white",
            bg=COLOR_BG
        ).pack()

        combo = ttk.Combobox(
            contenido,
            values=["Mensual", "Quincenal", "Semanal"],
            state="readonly"
        )
        combo.pack(pady=10)
        combo.current(0)

        def guardar():
            try:
                try:
                    monto=float(ent_monto_renov.get() or 0)
                except ValueError:
                    messagebox.showerror("Error", "El monto debe ser un número válido.")
                    return
                if monto < 0:
                    messagebox.showerror(
                        "Error",
                        "El monto no puede ser negativo."
                    )   
                    return
                modo = combo.get()
                hoy = datetime.now().date()

                try:
                    fecha_venc = datetime.strptime(
                        venc_actual,
                        "%Y-%m-%d"
                    ).date()
                except Exception:
                    fecha_venc = hoy

                base = fecha_venc if fecha_venc >= hoy else hoy

                nueva_fecha = base + timedelta(days=self.dias_pago(modo))

                with db_conn() as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        UPDATE clientes SET
                            ultimo_pago=?,
                            vencimiento=?,
                            modo_pago=?,
                            monto_pago=?
                        WHERE id=?
                    """, (
                        hoy.strftime("%Y-%m-%d"),
                        nueva_fecha.strftime("%Y-%m-%d"),
                        modo,
                        monto,
                        id_cliente
                    ))
                    cur.execute("""
                        INSERT INTO pagos(cliente_id, fecha, monto)
                        VALUES (?, ?, ?)
                    """, (
                        id_cliente,
                        hoy.strftime("%Y-%m-%d"),
                        monto
                    ))

                    conn.commit()

                if hasattr(self, 'ventana_estadisticas') and self.ventana_estadisticas.winfo_exists():
                    self.ventana_estadisticas.destroy()
                    self.abrir_panel_estadisticas()

                win.destroy()
                self.root.after(100, self.cargar_tabla)
                self.root.after(100, self.popup_ok)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo renovar:\n{str(e)}")

        tk.Button(
            contenido,
            text="RENOVAR",
            bg=COLOR_GREEN,
            fg="black",
            command=guardar
        ).pack(pady=20)

    # ------------------------------------------------------
    def popup_ok(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg="#00AA22")

        win.geometry("420x120+500+300")

        tk.Label(
            win,
            text="CLIENTE RENOVADO EXITOSAMENTE",
            font=("Arial Black", 12),
            fg="white",
            bg="#00AA22"
        ).pack(expand=True)

        win.after(1100, win.destroy)

    # ------------------------------------------------------
    def reproducir_alerta(self):
        def sonido():
            import time
            frecuencia = 2500 
            duracion_pulso = 80 
            pausa = 0.05

            for _ in range(10):
                winsound.Beep(frecuencia, duracion_pulso)
                time.sleep(pausa)
                
        threading.Thread(target=sonido, daemon=True).start()

if __name__ == "__main__":
    inicializar_bd()
    reparar_pagos_faltantes()
    root = tk.Tk()
    app = AtomGym(root)
    root.mainloop()