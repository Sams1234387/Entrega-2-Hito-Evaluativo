#Este archivo recibe lo que el usuario hace en el navegador, haciendo que cada clic llegue como un mensaje, lo traduce como un llamado que lo hace armar los datos en la pantalla que crea

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import exportador_excel
from datos_demo import cargar_datos_demo
from modelos import EstadoReserva, FORMATO_FECHA, FORMATO_HORA, Resultado
from reloj import Reloj
from repositorio import ErrorPersistencia, Repositorio
from servicio import ReglaNegocioError, ServicioSIGE

CARPETA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
TIPOS_ARCHIVO = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


#Esta clase junta el repositorio, el reloj y el servicio en un solo objeto 
class AplicacionSIGE:
    #Esta funcion se usa para la modificacion de variables 
    def __init__(self, carpeta_datos, abrir_archivos=True, exportar_excel=True):
        self.carpeta_datos = carpeta_datos
        self.abrir_archivos = abrir_archivos
        self.exportar_excel = exportar_excel
        self.reloj = Reloj()
        self.cerrojo = threading.RLock() #Rlock sirve para que dos pedidos no modifiquen los datos a la vez y reinciar_datos
        self._iniciar_datos()

    #Ocupa el rpositorio para empezar a iniciar los datos 
    def _iniciar_datos(self):
        self.repo = Repositorio(self.carpeta_datos, exportar_excel=self.exportar_excel)
        if self.repo.existe_base():
            self.repo.cargar()
            if self.exportar_excel:
                self.repo.sincronizar_excel()
        else:
            cargar_datos_demo(self.repo, self.reloj.ahora())
        self.servicio = ServicioSIGE(self.repo, self.reloj)

    #Funcion para reiniciar los datos a la hora que se se reciba una nueva solictiud 
    def reiniciar_datos(self):
        self.repo.vaciar()
        cargar_datos_demo(self.repo, self.reloj.ahora())


#Define el formato del texto de la hora y dia 
def _texto(momento):
    return momento.strftime("%Y-%m-%d %H:%M")


CODIGOS_TABLERO = (("OCUPADO", "OCUPADO"), ("LIBRE para", "LIBRE"), ("LIBRE (respaldo", "RESPALDO"),
                   ("BLOQUEADO", "BLOQUEADO"), ("NO liberado", "NO_LIBERADO"))


#Esta funcion se encarga de armar todos los datos que la pantalla necesita para dibujarse: propietarios, clientes, reservas, tablero y notificaciones
def construir_estado(app):
    s, repo = app.servicio, app.repo
    ahora = app.reloj.ahora()

    reservas = []
    for r in sorted(repo.reservas.values(), key=lambda r: r.id):
        cliente = repo.clientes.get(r.cliente_id)
        item = {
            "id": r.id, "cliente_id": r.cliente_id, "cliente": cliente.nombre if cliente else r.cliente_id,
            "patente": cliente.patente if cliente else "", "estacionamiento_id": r.estacionamiento_id,
            "propietario_id": r.propietario_id, "fecha": r.inicio.strftime(FORMATO_FECHA),
            "inicio": r.inicio.strftime(FORMATO_HORA), "fin": r.fin.strftime(FORMATO_HORA),
            "bloques": r.bloques, "estado": r.estado, "monto_total": r.monto_total,
            "monto_tarifa": r.monto_tarifa, "monto_penalizacion": r.monto_penalizacion,
            "motivo": r.motivo, "ya_comenzo": ahora >= r.inicio, "ya_termino": ahora >= r.fin,
        }
        if r.estado == EstadoReserva.PENDIENTE and r.inicio > ahora:
            item["compatibles"] = [{"id": e.id, "confiabilidad": e.confiabilidad}
                                   for e in s.estacionamientos_compatibles(r.inicio, r.fin)]
        if r.estado == EstadoReserva.CONFIRMADA and not item["ya_termino"]:
            item["destinos"] = [e.id for e in s.destinos_posibles(r)]
        reservas.append(item)

    tablero = []
    for est, texto in s.tablero(ahora):
        codigo = next((c for prefijo, c in CODIGOS_TABLERO if texto.startswith(prefijo)), "NO_LIBERADO")
        tablero.append({"id": est.id, "tipo": est.tipo, "estado": texto, "codigo": codigo})

    return {
        "ahora": _texto(ahora), "dia": ahora.strftime(FORMATO_FECHA), "simulado": app.reloj.es_simulado,
        "excel": {**repo.estado_excel, "ruta": repo.ruta_excel, "existe": os.path.exists(repo.ruta_excel),
                  "disponible": exportador_excel.DISPONIBLE},
        "propietarios": [{"id": p.id, "nombre": p.nombre, "rut": p.rut,
                          "estacionamiento": (s.estacionamiento_de(p.id).id if s.estacionamiento_de(p.id) else ""),
                          "confiabilidad": (s.estacionamiento_de(p.id).confiabilidad if s.estacionamiento_de(p.id) else 0),
                          "ingresos": s.ingresos_de_propietario(p.id)}
                         for p in sorted(repo.propietarios.values(), key=lambda p: p.id)],
        "clientes": [{"id": c.id, "nombre": c.nombre, "rut": c.rut, "patente": c.patente}
                     for c in sorted(repo.clientes.values(), key=lambda c: c.id)],
        "reservas": reservas,
        "tablero": tablero,
        "notificaciones": [{"id": n.id, "momento": _texto(n.momento), "tipo": n.destinatario_tipo,
                            "destinatario_id": n.destinatario_id, "nombre": n.destinatario_nombre,
                            "asunto": n.asunto, "mensaje": n.mensaje, "reserva_id": n.reserva_id}
                           for n in repo.notificaciones],
    }


#esta funcion se encarga de armar las fechas con su respectivo formato
def _valor_para_tabla(valor):
    if isinstance(valor, datetime):
        return _texto(valor)
    if hasattr(valor, "strftime"):
        return valor.strftime(FORMATO_FECHA)
    return valor


#Esta funcion se encarga de armar una hoja tipo Excel para mostrarle al presionar el boton de "Datos"
def construir_tabla(app, nombre, limite=300):
    tablas = exportador_excel.construir_tablas(app.repo)
    if nombre not in tablas:
        raise ReglaNegocioError(f"No existe la tabla {nombre}.")
    columnas, filas = tablas[nombre]
    total = len(filas)
    filas = filas[-limite:]
    return {"nombre": nombre, "columnas": columnas, "total": total,
            "filas": [[_valor_para_tabla(v) for v in fila] for fila in filas]}


#Esta funcion sirve para buscar una fecha y hora en la pagina, en caso de no sea valida maracara error 
def _momento(fecha, hora):
    try:
        return datetime.strptime(f"{fecha} {hora}", f"{FORMATO_FECHA} {FORMATO_HORA}")
    except (ValueError, TypeError):
        raise ReglaNegocioError("Fecha u hora no válida.")


#Funcion para buscar el estacionamiento de cada propietario 
def _estacionamiento_del(app, propietario_id):
    est = app.servicio.estacionamiento_de(propietario_id)
    if est is None:
        raise ReglaNegocioError("Ese propietario no tiene estacionamiento.")
    return est

#Las siguientes 16 funciones, una para cada boton de la pantalla, llaman a la opereacion de servicio y se muestra en pantalla

#Esta funcion es para la pestaña de propietarios, en especifico a la hora de presionar el boton de liberar estacionamiento 
def _liberar(app, d):
    n = app.servicio.liberar_estacionamiento(d["propietario_id"], _estacionamiento_del(app, d["propietario_id"]).id, _momento(d["fecha"], d["inicio"]), _momento(d["fecha"], d["fin"]))
    return f"{n} bloques liberados. Tu estacionamiento ya se puede reservar en ese horario."


#Funcion del propietario para bloquear su estacionamiento 
def _bloquear(app, d):
    resultados = app.servicio.bloquear_estacionamiento(
        d["propietario_id"], _estacionamiento_del(app, d["propietario_id"]).id,
        _momento(d["fecha"], d["inicio"]), _momento(d["fecha"], d["fin"]), d.get("motivo", ""))
    if not resultados:
        return "Estacionamiento bloqueado. No había reservas afectadas."
    partes = [f"reserva #{r['reserva']} → {r['destino']}" if r["accion"] == "REASIGNADA"
              else f"reserva #{r['reserva']} cancelada (reembolso total)" for r in resultados]
    return "Estacionamiento bloqueado. Contingencia: " + "; ".join(partes) + "."


#Esta funcion corresponde al boton en la pestaña de propietario para crear un rutina y asi no tener que liberar el espacio cada dia de forma manual
def _recurrente(app, d):
    hi = datetime.strptime(d["inicio"], FORMATO_HORA).time()
    hf = datetime.strptime(d["fin"], FORMATO_HORA).time()
    liberados, respetados = app.servicio.definir_horario_recurrente(
        d["propietario_id"], _estacionamiento_del(app, d["propietario_id"]).id,
        [int(x) for x in d.get("dias", [])], hi, hf, int(d.get("semanas", 2)))
    return f"Rutina aplicada: {liberados} bloques liberados ({respetados} bloqueos respetados)."


#Funcion para el boton de resgistro del cliente 
def _registrar_cliente(app, d):
    c = app.servicio.registrar_cliente(d.get("nombre", ""), d.get("rut", ""), d.get("patente", ""))
    return f"Cliente {c.id} ({c.nombre}) registrado."


#Funcion para reservar 
def _reservar(app, d):
    r = app.servicio.crear_reserva(d["cliente_id"], _momento(d["fecha"], d["inicio"]), _momento(d["fecha"], d["fin"]))
    return f"Reserva #{r.id} creada (valor ${r.monto_total:,}). Queda pendiente hasta que el administrador la asigne.".replace(",", ".")


#Boton para cancelar el arriendo
def _cancelar(app, d):
    r = app.servicio.cancelar_reserva(d["cliente_id"], int(d["reserva_id"]))
    return f"Reserva cancelada. Reembolso ${r['reembolso']:,}, penalización ${r['penalizacion']:,}.".replace(",", ".")


#Boton para cuando el cliente no use todo el tiempo que agendo y pueda liberar el espacio no ocupado
def _liberar_reserva(app, d):
    r = app.servicio.liberar_reserva(d["cliente_id"], int(d["reserva_id"]))
    return (f"Reserva liberada. Usaste {r['bloques_usados']} bloque(s): cobrado ${r['cobrado']:,}, "
            f"reembolso ${r['reembolso']:,}.").replace(",", ".")


#Boton para el cliente que lo deja extender su plazo de timepo simepre y cuando no existan mas arriendos despues o que no se pase de la hora tope
def _extender(app, d):
    cobro = app.servicio.extender_reserva(d["cliente_id"], int(d["reserva_id"]), int(d["bloques"]))
    return f"Reserva extendida. Cobro adicional ${cobro:,}.".replace(",", ".")


# Boton para la pestaña de operador, este boton permitira asignar en los estacionamientos disponibles a los arriendos pendientes 
def _asignar(app, d):
    est = app.servicio.asignar_reserva(int(d["reserva_id"]), d.get("estacionamiento_id") or None)
    return f"Reserva #{d['reserva_id']} confirmada en {est.id}. Se notificó al cliente y al propietario."


#Boton para cuando un estacionamiento se bloquea por orden del propietario, y el operador deba usar este boton para mover un arriendo a otro estacionamiento
def _reasignar(app, d):
    est = app.servicio.reasignar_reserva(int(d["reserva_id"]), d["destino"], d.get("motivo") or "reasignación manual")
    return f"Reserva #{d['reserva_id']} reasignada a {est.id}."


#Boton para cerrar un arriendo por los distintos motivos posibles 
def _cerrar(app, d):
    r = app.servicio.registrar_resultado(int(d["reserva_id"]), d["resultado"], int(d.get("exceso", 0) or 0))
    return f"Reserva #{r.id} cerrada como {r.estado}."


#boton para simular una hora 
def _reloj_fijar(app, d):
    app.reloj.fijar(_momento(d["fecha"], d["hora"]))
    return f"Hora simulada: {_texto(app.reloj.ahora())}."


#Boton para hacer avanzar la hora dentro del sistema
def _reloj_avanzar(app, d):
    app.reloj.avanzar(int(d["minutos"]))
    return f"Hora simulada: {_texto(app.reloj.ahora())}."


#boton para que el reloj de Sige sea el mismo que el del sistema, osea la hora real 
def _reloj_real(app, d):
    app.reloj.usar_hora_real()
    return "Usando la hora real del computador."


#Boton para el reinicio de datos para crear unos nuevos en base la nueva fecha estabelcida 
def _reiniciar(app, d):
    app.reiniciar_datos()
    return "Datos de demostración recreados desde la fecha del reloj."


# boton para saber donde se guardan los datos dentro de la computadora 
def abrir_programa(ruta):
    if sys.platform.startswith("win"):
        os.startfile(ruta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


#Boton para abrir el excel que contienelos datos del programa, es una copia ya que si se abrirera el original el sistema no permitiria seguir escribiendolo 
def _abrir_excel(app, d):
    if not exportador_excel.DISPONIBLE:
        raise ReglaNegocioError("Falta instalar openpyxl para generar el Excel: pip install openpyxl")
    app.repo.sincronizar_excel()
    if not os.path.exists(app.repo.ruta_excel):
        raise ReglaNegocioError("Todavía no se pudo generar el Excel.")
    copia = os.path.join(tempfile.gettempdir(), f"SIGE_vista_{datetime.now():%H%M%S}.xlsx")
    shutil.copyfile(app.repo.ruta_excel, copia)
    if app.abrir_archivos:
        abrir_programa(copia)
    return f"Se abrió una copia del Excel actualizada a las {datetime.now():%H:%M:%S}. Vuelve a apretar el botón para ver los cambios nuevos."


ACCIONES = {
    "liberar": _liberar, "bloquear": _bloquear, "recurrente": _recurrente,
    "registrar_cliente": _registrar_cliente, "reservar": _reservar, "cancelar": _cancelar,
    "liberar_reserva": _liberar_reserva, "extender": _extender,
    "asignar": _asignar, "reasignar": _reasignar, "cerrar": _cerrar,
    "reloj_fijar": _reloj_fijar, "reloj_avanzar": _reloj_avanzar, "reloj_real": _reloj_real,
    "reiniciar": _reiniciar, "abrir_excel": _abrir_excel,
}


# Ejecuta una acción y responde de una de tres formas: salió bien, una regla de negocio la rechazó (con el motivo), o la operación se hizo pero no se pudo guardar un archivo
def ejecutar_accion(app, datos):
    nombre = datos.get("accion")
    if nombre not in ACCIONES:
        return {"ok": False, "error": f"Acción desconocida: {nombre}"}
    try:
        with app.cerrojo:
            mensaje = ACCIONES[nombre](app, datos)
        return {"ok": True, "mensaje": mensaje}
    except ReglaNegocioError as problema:
        return {"ok": False, "error": str(problema)}
    except ErrorPersistencia as problema:
        return {"ok": True, "mensaje": "La operación se realizó.", "advertencia": str(problema)}
    except (KeyError, ValueError) as problema:
        return {"ok": False, "error": f"Faltan datos o son inválidos: {problema}"}


#Define a qué direcciones responde el servidor (/api/estado, /api/accion, /api/mapa, /api/tabla, /descargar/excel) y evita que se pidan archivos fuera de la carpeta web
def crear_manejador(app):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, formato, *argumentos):
            pass
        def _responder(self, codigo, contenido, tipo="application/json; charset=utf-8", extra=None):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            for clave, valor in (extra or {}).items():
                self.send_header(clave, valor)
            self.end_headers()
            self.wfile.write(contenido)
        def _json(self, datos, codigo=200):
            self._responder(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"))

        def do_GET(self):
            ruta = urlparse(self.path)
            consulta = parse_qs(ruta.query)
            try:
                if ruta.path == "/api/estado":
                    with app.cerrojo:
                        return self._json(construir_estado(app))
                if ruta.path == "/api/mapa":
                    with app.cerrojo:
                        dia = datetime.strptime(consulta["fecha"][0], FORMATO_FECHA).date()
                        filas = app.servicio.mapa_dia(consulta["estacionamiento"][0], dia)
                    return self._json([{"hora": b.strftime(FORMATO_HORA), "simbolo": s} for b, s in filas])
                if ruta.path == "/api/tabla":
                    with app.cerrojo:
                        return self._json(construir_tabla(app, consulta["nombre"][0]))
                if ruta.path == "/descargar/excel":
                    with app.cerrojo:
                        app.repo.sincronizar_excel()
                        if not os.path.exists(app.repo.ruta_excel):
                            return self._json({"ok": False, "error": "El Excel todavía no existe."}, 404)
                        with open(app.repo.ruta_excel, "rb") as archivo:
                            contenido = archivo.read()
                    return self._responder(200, contenido,
                                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                           {"Content-Disposition": 'attachment; filename="SIGE_datos.xlsx"'})
                return self._servir_archivo(ruta.path)
            except ReglaNegocioError as problema:
                return self._json({"ok": False, "error": str(problema)}, 400)
            except (KeyError, ValueError, IndexError) as problema:
                return self._json({"ok": False, "error": f"Pedido inválido: {problema}"}, 400)
            except Exception:
                traceback.print_exc()
                return self._json({"ok": False, "error": "Error interno del servidor (ver la consola)."}, 500)

        def _servir_archivo(self, ruta):
            nombre = "index.html" if ruta in ("", "/") else ruta.lstrip("/")
            destino = os.path.normpath(os.path.join(CARPETA_WEB, nombre))
            if not destino.startswith(CARPETA_WEB) or not os.path.isfile(destino):
                return self._json({"ok": False, "error": "No encontrado"}, 404)
            with open(destino, "rb") as archivo:
                contenido = archivo.read()
            tipo = TIPOS_ARCHIVO.get(os.path.splitext(destino)[1], "application/octet-stream")
            self._responder(200, contenido, tipo)

        def do_POST(self):
            if urlparse(self.path).path != "/api/accion":
                return self._json({"ok": False, "error": "No encontrado"}, 404)
            try:
                largo = int(self.headers.get("Content-Length", 0))
                datos = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return self._json({"ok": False, "error": "Mensaje inválido"}, 400)
            try:
                return self._json(ejecutar_accion(app, datos))
            except Exception:
                traceback.print_exc()
                return self._json({"ok": False, "error": "Error interno del servidor (ver la consola)."}, 500)

    return Manejador


#Busca un puerto libre y lanza un hilo que reintenta escribir el Excel si estaba bloqueado
def iniciar_servidor(app, puerto=8765, intentos=20):
    ultimo_error = None
    for numero in range(puerto, puerto + intentos):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", numero), crear_manejador(app))
            break
        except OSError as problema:
            ultimo_error = problema
    else:
        raise ultimo_error

    #Como dice su nombre reintenta abrir el excel en caso de no funcionar
    def reintentar_excel():
        while True:
            threading.Event().wait(2)
            with app.cerrojo:
                if app.repo.excel_pendiente:
                    app.repo.sincronizar_excel()

    threading.Thread(target=reintentar_excel, daemon=True).start()
    return servidor