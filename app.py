from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date, datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.units import mm


app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('catequesis.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    hoy = datetime.today().strftime('%Y-%m-%d')
    participantes = conn.execute('SELECT * FROM participantes WHERE activo = 1').fetchall()
    conn.close()
    return render_template('index.html', participantes=participantes, hoy=hoy, fecha=hoy)

@app.route('/registrar_asistencia', methods=['POST'])
def registrar_asistencia():
    conn = get_db_connection()
    fecha = request.form['fecha']
    presentes = request.form.getlist('asistencia')

    # Eliminar asistencias previas de esa fecha
    conn.execute('DELETE FROM asistencias WHERE fecha = ?', (fecha,))
    
    participantes = conn.execute('SELECT id FROM participantes WHERE activo = 1').fetchall()

    for p in participantes:
        presente = 1 if str(p['id']) in presentes else 0
        conn.execute(
            'INSERT INTO asistencias (fecha, participante_id, presente) VALUES (?, ?, ?)',
            (fecha, p['id'], presente)
        )

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Ruta para mostrar el formulario
@app.route('/nuevo_participante')
def nuevo_participante():
    return render_template('nuevo_participante.html')

# Ruta para guardar el nuevo participante
@app.route('/guardar_participante', methods=['POST'])
def guardar_participante():
    nombre = request.form['nombre']
    edad = request.form['edad']
    grupo = request.form['grupo']
    contacto = request.form['contacto']

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO participantes (nombre, edad, grupo, contacto) VALUES (?, ?, ?, ?)',
        (nombre, edad, grupo, contacto)
    )
    conn.commit()
    conn.close()

    return redirect('/')

@app.route('/historial/<int:participante_id>')
def historial(participante_id):
    conn = get_db_connection()

    participante = conn.execute(
        'SELECT * FROM participantes WHERE id = ?',
        (participante_id,)
    ).fetchone()

    asistencias = conn.execute(
        'SELECT fecha, presente, observacion FROM asistencias WHERE participante_id = ? ORDER BY fecha DESC',
        (participante_id,)
    ).fetchall()

    conn.close()

    total_asistencias = sum(1 for a in asistencias if a['presente'] == 1)

    return render_template('historial.html', participante=participante, asistencias=asistencias, total_asistencias=total_asistencias)

@app.route('/editar_participante/<int:id>')
def editar_participante(id):
    conn = get_db_connection()
    participante = conn.execute('SELECT * FROM participantes WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar_participante.html', participante=participante)

@app.route('/actualizar_participante/<int:id>', methods=['POST'])
def actualizar_participante(id):
    nombre = request.form['nombre']
    edad = request.form['edad']
    grupo = request.form['grupo']
    contacto = request.form['contacto']

    conn = get_db_connection()
    conn.execute('''
        UPDATE participantes SET nombre = ?, edad = ?, grupo = ?, contacto = ?
        WHERE id = ?
    ''', (nombre, edad, grupo, contacto, id))
    conn.commit()
    conn.close()
    return redirect(f'/historial/{id}')

@app.route('/eliminar_participante/<int:id>', methods=['POST'])
def eliminar_participante(id):
    conn = get_db_connection()
    conn.execute('UPDATE participantes SET activo = 0 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/reporte', methods=['GET', 'POST'])
def reporte():
    conn = get_db_connection()
    participantes = conn.execute('SELECT * FROM participantes WHERE activo = 1').fetchall()

    if request.method == 'POST':
        fecha = request.form['fecha']
        observaciones = request.form.getlist('observacion')
        presentes_ids = request.form.getlist('presente')  # checkbox marcados

        # Borrar registros anteriores de esa fecha
        conn.execute('DELETE FROM asistencias WHERE fecha = ?', (fecha,))
        conn.commit()

        for idx, p in enumerate(participantes):
            presente = 1 if str(p['id']) in presentes_ids else 0
            observacion = observaciones[idx] if idx < len(observaciones) else ""
            conn.execute('''
                INSERT INTO asistencias (fecha, participante_id, presente, observacion)
                VALUES (?, ?, ?, ?)
            ''', (fecha, p['id'], presente, observacion))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('reporte.html', participantes=participantes)


@app.route('/descargar_pdf', methods=['POST'])
def descargar_pdf():
    conn = get_db_connection()
    resultados = conn.execute('''
        SELECT p.nombre, p.grupo, a.fecha, a.presente, a.observacion
        FROM asistencias a
        JOIN participantes p ON a.participante_id = p.id
        ORDER BY a.fecha DESC, p.nombre
    ''').fetchall()
    conn.close()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Reporte Completo de Asistencia")

    y = height - 80
    c.setFont("Helvetica", 12)

    if not resultados:
        c.drawString(50, y, "No hay registros de asistencia.")
    else:
        # Agrupar resultados por fecha
        from collections import defaultdict
        asistencias_por_fecha = defaultdict(list)
        for r in resultados:
            asistencias_por_fecha[r['fecha']].append(r)

        # Para cada fecha, dibujamos un cuadro con la fecha y la lista
        for fecha, registros in sorted(asistencias_por_fecha.items(), reverse=True):
            # Espacio para el cuadro
            cuadro_altura = 20 + 20 * len(registros)
            if y - cuadro_altura < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 12)

            # Dibujar rectángulo para la fecha (cuadro)
            margen_izq = 45
            cuadro_ancho = width - 2 * margen_izq
            c.setStrokeColor(colors.HexColor("#3b82f6"))
            c.setLineWidth(1)
            c.rect(margen_izq, y - cuadro_altura, cuadro_ancho, cuadro_altura, stroke=1, fill=0)

            # Fecha como título del cuadro
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margen_izq + 10, y - 20, f"Fecha: {fecha}")
            c.setFont("Helvetica", 12)

            # Listar asistencias de esa fecha
            y_linea = y - 40
            for r in registros:
                presente_texto = "Sí" if r['presente'] else "No"
                texto = f"{r['nombre']} ({r['grupo']}) - Presente: {presente_texto} - Observación: {r['observacion'] or 'Sin observación'}"
                c.drawString(margen_izq + 15, y_linea, texto)
                y_linea -= 20

            y -= cuadro_altura + 15  # espacio entre cuadros

    c.save()
    buffer.seek(0)

    return send_file(buffer,
                     as_attachment=True,
                     download_name="reporte_completo_asistencia.pdf",
                     mimetype='application/pdf')

@app.route('/porcentajes')
def porcentajes():
    conn = get_db_connection()

    total_dias = conn.execute('SELECT COUNT(DISTINCT fecha) FROM asistencias').fetchone()[0]
    participantes = conn.execute('SELECT * FROM participantes WHERE activo = 1').fetchall()


    porcentaje_list = []
    for p in participantes:
        asistencias = conn.execute('''
            SELECT COUNT(*) FROM asistencias WHERE participante_id = ? AND presente = 1
        ''', (p['id'],)).fetchone()[0]

        porcentaje = (asistencias / total_dias * 100) if total_dias > 0 else 0
        porcentaje_list.append({
            'id': p['id'],
            'nombre': p['nombre'],
            'grupo': p['grupo'],
            'porcentaje': round(porcentaje, 2)
        })

    conn.close()
    return render_template('porcentajes.html', participantes=porcentaje_list, total_dias=total_dias)


#if __name__ == '__main__':
#    app.run(debug=True)
