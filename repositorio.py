#Guarda los datos del sistema y los recupera
#Mientras el programa corre, todo vive en memoria (diccionarios y listas)
#Después de cada operación, guardar() escribe ese estado en archivos CSV y actualiza el Excel
#Al volver a abrir el programa, cargar() reconstruye todo desde los archivos. 

import csv
import os

import exportador_excel
from datetime import datetime
from modelos import (Propietario, Cliente, Estacionamiento, Reserva, Evento, 
                     Liquidacion, Notificacion, a_fila, desde_fila)
from dataclasses import fields

CODIFICACION = "utf-8-sig"  #Formato para trabajas datos en forma de Excel o scv

#Clase que aparece cuando no se puede escribir un CSV
class ErrorPersistencia(Exception):
    pass

#Clase principal del programa
class Repositorio:
    #Funcion encargada de crear los Diccionarios y Listas, propietarios, clientes, estacionamientos, reservas, disponibilidad, historial, liquidaciones y notificaciones. En disponibilidad, cada bloque se identifica con la pareja (id del estacionamiento, "2026-10-27 09:30") y vale LIBERADO o BLOQUEADO
    def __init__(self, carpeta="datos", exportar_excel=True):
        self.carpeta = carpeta
        self.exportar_excel = exportar_excel
        self.ruta_excel = os.path.join(carpeta, "SIGE_datos.xlsx")
        self.estado_excel = {"estado": "PENDIENTE", "ultima": "", "mensaje": ""}
        self.propietarios = {}
        self.clientes = {}
        self.estacionamientos = {}
        self.reservas = {}
        self.disponibilidad = {}
        self.historial = []
        self.liquidaciones = []
        self.notificaciones = []

    #Borra todo lo que hay en memoria, ejemplo reiniciar los datos de demostracion
    def vaciar(self):
        self.propietarios, self.clientes, self.estacionamientos = {}, {}, {}
        self.reservas, self.disponibilidad = {}, {}
        self.historial, self.liquidaciones, self.notificaciones = [], [], []

    #Funcion que estblece la ruta o donde se guardara el archivo dentro de la computadora 
    def _ruta(self, nombre):
        return os.path.join(self.carpeta, nombre)

    #Se encarga de verificar e indicar si ya hay datos guardados de una ejecucion anterior 
    def existe_base(self):
        return os.path.exists(self._ruta("estacionamientos.csv"))

    #Las funciones "siguiente_id" calculan el proximo numero, por eso se usa max() + 1
    def siguiente_id_reserva(self):
        return max(self.reservas.keys(), default=0) + 1


    def siguiente_id_evento(self):
        return max((e.id for e in self.historial), default=0) + 1

    
    def siguiente_id_notificacion(self):
        return max((n.id for n in self.notificaciones), default=0) + 1

    
    def siguiente_id_cliente(self):
        numeros = [int(c[1:]) for c in self.clientes if c[1:].isdigit()]
        return "C%02d" % (max(numeros, default=0) + 1)

    #Funcion que escribe un CSV de forma segura usando un archivo temporal 
    def _escribir(self, nombre, campos, filas):
        os.makedirs(self.carpeta, exist_ok=True)
        ruta = self._ruta(nombre)
        temporal = ruta + ".tmp"
        with open(temporal, "w", newline="", encoding=CODIFICACION) as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows(filas)
        try:
            #El archivo original se reemplaza solo cuando el temporal esta completo para evitar cuaalquier tipo de error que se pueda generar 
            os.replace(temporal, ruta)
        except PermissionError:
            os.remove(temporal)
            raise ErrorPersistencia(
                f"No se pudo guardar '{nombre}' porque está abierto en otro programa (¿Excel?). "
                f"Ciérralo: los cambios siguen en memoria y se guardarán en la próxima operación.")

    #Una vez que el archivo original se reemplaza con el temporal completo, con esta funcion se guardan esos datos, se escriben 8 archivos SCV y se actualiza el Excel 
    def guardar(self):
        #Esa función obtiene los nombres de las columnas para el encabezado de cada CSV
        def nombres(clase):
            return [c.name for c in fields(clase)]

        self._escribir("propietarios.csv", nombres(Propietario),
                       [a_fila(p) for p in self.propietarios.values()])
        self._escribir("clientes.csv", nombres(Cliente),
                       [a_fila(c) for c in self.clientes.values()])
        self._escribir("estacionamientos.csv", nombres(Estacionamiento),
                       [a_fila(e) for e in self.estacionamientos.values()])
        self._escribir("reservas.csv", nombres(Reserva),
                       [a_fila(r) for r in sorted(self.reservas.values(), key=lambda r: r.id)])
        self._escribir("historial.csv", nombres(Evento), [a_fila(e) for e in self.historial])
        self._escribir("liquidaciones.csv", nombres(Liquidacion),
                       [a_fila(l) for l in self.liquidaciones])
        self._escribir("notificaciones.csv", nombres(Notificacion),
                       [a_fila(n) for n in self.notificaciones])
        filas_disp = [{"estacionamiento_id": est, "bloque": bloque, "estado": estado}
                      for (est, bloque), estado in sorted(self.disponibilidad.items())]
        self._escribir("disponibilidad.csv", ["estacionamiento_id", "bloque", "estado"], filas_disp)
        if self.exportar_excel:
            self.sincronizar_excel()

    #Funcion ecargada de ir actualizando el Excel y nunca detener el programa, en caso de que lo haga se dejara el motivo en "estado_excel"
    def sincronizar_excel(self):
        if not exportador_excel.DISPONIBLE:
            self.estado_excel = {"estado": "SIN_OPENPYXL", "ultima": "",
                                 "mensaje": "Falta instalar openpyxl: ejecuta  pip install openpyxl"}
            return False
        try:
            exportador_excel.escribir_excel(self, self.ruta_excel)
        except PermissionError:
            self.estado_excel = {"estado": "BLOQUEADO", "ultima": self.estado_excel.get("ultima", ""),
                                 "mensaje": "El Excel está abierto en otro programa. Se actualizará solo "
                                            "cuando lo cierres; mientras tanto usa 'Abrir Excel' para ver una copia."}
            return False
        except OSError as problema:
            self.estado_excel = {"estado": "ERROR", "ultima": self.estado_excel.get("ultima", ""),
                                 "mensaje": f"No se pudo escribir el Excel: {problema}"}
            return False
        self.estado_excel = {"estado": "OK", "ultima": datetime.now().strftime("%H:%M:%S"), "mensaje": ""}
        return True

    #Se verifica si hay que volver a intentar volver a escribir el excel 
    @property
    def excel_pendiente(self):
        return self.exportar_excel and self.estado_excel["estado"] in ("BLOQUEADO", "ERROR")

    #Las siguientes funciones se encargas de leer los CSV y reconstruyen los objetos al volver a abrir el programa 
    def _leer(self, nombre):
        ruta = self._ruta(nombre)
        if not os.path.exists(ruta):
            return []
        with open(ruta, newline="", encoding=CODIFICACION) as archivo:
            return list(csv.DictReader(archivo))

    
    def cargar(self):
        self.propietarios = {f["id"]: desde_fila(Propietario, f) for f in self._leer("propietarios.csv")}
        self.clientes = {f["id"]: desde_fila(Cliente, f) for f in self._leer("clientes.csv")}
        self.estacionamientos = {f["id"]: desde_fila(Estacionamiento, f)
                                 for f in self._leer("estacionamientos.csv")}
        self.reservas = {int(f["id"]): desde_fila(Reserva, f) for f in self._leer("reservas.csv")}
        self.historial = [desde_fila(Evento, f) for f in self._leer("historial.csv")]
        self.liquidaciones = [desde_fila(Liquidacion, f) for f in self._leer("liquidaciones.csv")]
        self.notificaciones = [desde_fila(Notificacion, f) for f in self._leer("notificaciones.csv")]
        self.disponibilidad = {(f["estacionamiento_id"], f["bloque"]): f["estado"]
                               for f in self._leer("disponibilidad.csv")}


#csv.DictWriter y csv.DictReader escriben y leen filas como diccionarios con nombre de las columnas

#{f["id"]: desde_fila(Cliente, f) for f in filas} crea un diccionario recorriendo una lista en una sola linea 
#encoding ="utf-8-sig" hace que Excel muestre bien las tildes de los CSV 
#max(..., default=0) es el maximo de una lista o dara 0 si esta esta vacia 
#os.replace cambia un archivo del sistema en tan solo un paso 