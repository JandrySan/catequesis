import sqlite3

conn = sqlite3.connect('catequesis.db')
c = conn.cursor()

# Crear tabla de participantes
c.execute('''
    CREATE TABLE IF NOT EXISTS participantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        edad INTEGER,
        grupo TEXT,
        contacto TEXT,
        activo BOOLEAN DEFAULT 1
    )
''')

# Crear tabla de asistencias con la columna 'presente'
c.execute('''
    CREATE TABLE IF NOT EXISTS asistencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        participante_id INTEGER NOT NULL,
        presente INTEGER DEFAULT 0,  -- 0=no asistió, 1=asistió
        observacion TEXT,
        FOREIGN KEY (participante_id) REFERENCES participantes (id)
    )
''')

conn.commit()
conn.close()
print("Base de datos creada correctamente con la columna 'presente'.")
