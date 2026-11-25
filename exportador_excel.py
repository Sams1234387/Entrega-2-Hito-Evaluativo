#Este codigo es el que genera un archivo .xlsx con una hoja por tabal y una hoja de Resumen, para ver los datos del programa via Excel, los datos se van modificando en tiempo real cuando el programa sufre de una modificacion

import os
from collections import Counter 
from datetime import datetime

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    DISPONIBLE = True   #Disponible indica que openpyxl este instalada, en caso de que no lo este el sistema funciona igual
except ImportError:
    DISPONIBLE = False

FORMATO_FECHA_HORA = "yyyy-mm-dd hh:mm"
FORMATO_PESOS = '"$"#,##0'


#Funcion para indicar en que momento del dia ocurre cada cosa
def _dia(momento):
    return momento.date() if isinstance(momento, datetime) else momento

#Funcion central, esta creara 8 tablas deonde se encuentren los datos del programa, Reservas, actores, pagos, mensajes/notifiaciones, disponibilidad, Estacionamientos, esta funcion alimentara el excel y la pestaña llamada "Datos" mostrada en la pantalla
def construir_tablas(repo):
    tablas = {}

    filas = []
    for r in sorted(repo.reservas.values(), key=lambda r: r.id):
        cliente = repo.clientes.get(r.cliente_id)
        filas.append([r.id, cliente.nombre if cliente else r.cliente_id,
                      cliente.patente if cliente else "", r.estacionamiento_id or "sin asignar",
                      r.propietario_id, r.inicio.date(), r.inicio.strftime("%H:%M"),
                      r.fin.strftime("%H:%M"), r.bloques, r.estado, r.monto_total,
                      r.monto_tarifa, r.monto_penalizacion, r.motivo, r.creada_en])
    tablas["Reservas"] = (["Reserva", "Cliente", "Patente", "Estacionamiento", "Propietario", "Fecha",
                           "Hora inicio", "Hora término", "Bloques", "Estado", "Valor total",
                           "Tarifa cobrada", "Penalización", "Motivo", "Creada"], filas)

    tablas["Historial"] = (
        ["Evento", "Momento", "Tipo", "Reserva", "Estacionamiento", "Propietario", "Cliente", "Fecha",
         "Hora inicio", "Hora término", "Estado", "Monto", "Detalle"],
        [[e.id, e.momento, e.tipo, e.reserva_id, e.estacionamiento_id, e.propietario_id, e.cliente_id,
          e.fecha, e.hora_inicio, e.hora_fin, e.estado, e.monto, e.detalle] for e in repo.historial])

    tablas["Liquidaciones"] = (
        ["Reserva", "Momento", "Fecha", "Estacionamiento", "Propietario", "Tarifa", "Penalización",
         "A propietario", "A operador", "A administración"],
        [[l.reserva_id, l.momento, l.fecha, l.estacionamiento_id, l.propietario_id, l.monto_tarifa,
          l.monto_penalizacion, l.a_propietario, l.a_operador, l.a_administracion]
         for l in repo.liquidaciones])

    tablas["Notificaciones"] = (
        ["N°", "Momento", "Para (tipo)", "Id", "Nombre", "Asunto", "Mensaje", "Reserva", "Canal"],
        [[n.id, n.momento, n.destinatario_tipo, n.destinatario_id, n.destinatario_nombre, n.asunto,
          n.mensaje, n.reserva_id, n.canal] for n in repo.notificaciones])

    filas = []
    for (est_id, bloque), estado in sorted(repo.disponibilidad.items()):
        fecha, hora = bloque.split(" ")
        filas.append([est_id, fecha, hora, estado])
    tablas["Disponibilidad"] = (["Estacionamiento", "Fecha", "Hora (bloque de 30 min)", "Estado"], filas)

    tablas["Estacionamientos"] = (
        ["Estacionamiento", "Tipo", "Propietario", "Confiabilidad histórica"],
        [[e.id, e.tipo, e.propietario_id, e.confiabilidad] for e in repo.estacionamientos.values()])
    tablas["Propietarios"] = (["Id", "Nombre", "RUT"],
                              [[p.id, p.nombre, p.rut] for p in repo.propietarios.values()])
    tablas["Clientes"] = (["Id", "Nombre", "RUT", "Patente"],
                          [[c.id, c.nombre, c.rut, c.patente] for c in repo.clientes.values()])
    return tablas

#Funcion que genera la hoja "Resumen", aqui se encuentran solo las reservas por su estado, y el dinero total 
def _resumen(repo):
    por_estado = Counter(r.estado for r in repo.reservas.values())
    filas = [("Última actualización", datetime.now().strftime("%Y-%m-%d %H:%M:%S")), ("", "")]
    filas.append(("RESERVAS POR ESTADO", ""))
    for estado in ("PENDIENTE", "CONFIRMADA", "CANCELADA", "LIBERADA", "FINALIZADA", "NO_PRESENTADA"):
        filas.append((estado, por_estado.get(estado, 0)))
    filas.append(("Total de reservas", len(repo.reservas)))
    filas += [("", ""), ("DINERO (CLP)", "")]
    filas.append(("Tarifa cobrada en reservas", sum(r.monto_tarifa for r in repo.reservas.values())))
    filas.append(("Penalizaciones cobradas", sum(r.monto_penalizacion for r in repo.reservas.values())))
    filas.append(("Repartido a propietarios / comunidad", sum(l.a_propietario for l in repo.liquidaciones)))
    filas.append(("Repartido al operador", sum(l.a_operador for l in repo.liquidaciones)))
    filas.append(("Repartido a la administración", sum(l.a_administracion for l in repo.liquidaciones)))
    filas += [("", ""), ("ACTIVIDAD", "")]
    filas.append(("Eventos en el historial", len(repo.historial)))
    filas.append(("Notificaciones enviadas", len(repo.notificaciones)))
    return filas


#Las siguientes dos funciones se enfocan en la parte mas estetica del Excel creado, colores, ancho, y los formatos
def _estilo_encabezado(hoja, n_columnas):
    relleno = PatternFill("solid", fgColor="1F3864")
    for col in range(1, n_columnas + 1):
        celda = hoja.cell(row=1, column=col)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    hoja.freeze_panes = "A2"

def _formatear(hoja, columnas, filas):
    for indice, nombre in enumerate(columnas, 1):
        letra = get_column_letter(indice)
        largo = max([len(str(nombre))] + [len(str(f[indice - 1])) for f in filas[:300]] + [8])
        hoja.column_dimensions[letra].width = min(largo + 3, 70 if nombre == "Mensaje" else 45)
        es_dinero = any(p in nombre for p in ("Valor", "Tarifa", "Penaliz", "Monto", "A propietario",
                                              "A operador", "A administración"))
        for fila in range(2, len(filas) + 2):
            celda = hoja.cell(row=fila, column=indice)
            if isinstance(celda.value, datetime):
                celda.number_format = FORMATO_FECHA_HORA
            elif es_dinero and isinstance(celda.value, (int, float)):
                celda.number_format = FORMATO_PESOS
            elif nombre == "Confiabilidad histórica":
                celda.number_format = "0%"
            elif nombre == "Mensaje":
                celda.alignment = Alignment(wrap_text=True, vertical="top")
    if filas:
        hoja.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}{len(filas) + 1}"


#Esta funcion es de las mas importantes ya que es la que escribe el Excel, con las funciones que se le dieron antes 
def escribir_excel(repo, ruta):
    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    resumen.append(["Concepto", "Valor"])
    for concepto, valor in _resumen(repo):
        resumen.append([concepto, valor])
    _estilo_encabezado(resumen, 2)
    resumen.column_dimensions["A"].width = 42
    resumen.column_dimensions["B"].width = 24
    for fila in range(2, resumen.max_row + 1):
        concepto = resumen.cell(row=fila, column=1)
        if concepto.value and str(concepto.value).isupper():
            concepto.font = Font(bold=True, color="1F3864")
        valor = resumen.cell(row=fila, column=2)
        if isinstance(valor.value, int) and any(p in str(concepto.value) for p in ("cobrada", "Penaliz", "Repartido")):
            valor.number_format = FORMATO_PESOS

    for nombre, (columnas, filas) in construir_tablas(repo).items():
        hoja = libro.create_sheet(nombre)
        hoja.append(columnas)
        for fila in filas:
            hoja.append(fila)
        _estilo_encabezado(hoja, len(columnas))
        _formatear(hoja, columnas, filas)

    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    temporal = ruta[:-5] + ".tmp.xlsx"
    libro.save(temporal)
    try:
        os.replace(temporal, ruta)
    except PermissionError:
        os.remove(temporal)
        raise


#try / expect ImportError: es para importar librerias y en caso de que no esten instaladas el sistema no falla, simplemente indica la asuencia de la libreria 
#Counter cuenta cuentas veces aparece cada elemento(reservas por estado)
#os.Replace cambia el archivo real recien cuando el temporal quedo completo, si esta abierto no dejara reemplazarlo

