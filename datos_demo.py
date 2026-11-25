#Archivo que creara al edificio de ejemplo para que al principio el programa no este vacio y se puedan probar las funciones de la aplicacion, sin el, el programa partiria sin clientes, dueños y habira que poner todo de forma manual 

from datetime import timedelta
from modelos import (Propietario, Cliente, Estacionamiento, TipoEstacionamiento, COMUNIDAD, EstadoBloque, bloques_entre, clave_bloque)

PROPIETARIOS= [
    ("P01","Samuel Abdala","22.320.026-5","E18", 0.990),
    ("P02", "Jorge Fuentes", "12.222.222-2", "E05", 0.980),
    ("P03", "Camila Soto", "13.333.333-3", "E16", 0.935),
    ("P04", "Andrés Vidal", "14.444.444-4", "E12", 0.928),
    ("P05", "Paula Núñez", "15.555.555-5", "E11", 0.922),
    ("P06", "Luis Herrera", "16.666.666-6", "E33", 0.242),
    ("P07", "Sofía Araya", "17.777.777-7", "E34", 0.288),
    ("P08", "Ricardo Pino", "18.888.888-8", "E37", 0.328),
]

CLIENTES = [
    ("C01", "Daniela Castro", "19.111.111-1", "BCDF12"),
    ("C02", "Felipe Muñoz", "19.222.222-2", "GHJK34"),
    ("C03", "Valentina Díaz", "19.333.333-3", "LMNP56"),
    ("C04", "Tomás Bravo", "19.444.444-4", "RSTV78"),
]

PARTICIPANTES = ["E18", "E05", "E16", "E12", "E11"]

#Esta siguiente funcion crea los propietarios, clientes y estacionamientos (8 privados y 2 de visita, V1 y V2), y libera de lunes a viernes de 08:30 a 18:00 los bloques de los próximos 14 días para los participantes
def cargar_datos_demo(repositorio, desde, dias=14):
    for pid, nombre, rut, _, _ in PROPIETARIOS:
        repositorio.propietarios[pid] = Propietario(id=pid, nombre=nombre, rut=rut)
    for cid, nombre, rut, patente in CLIENTES:
        repositorio.clientes[cid] = Cliente(id=cid, nombre=nombre, rut=rut, patente=patente)
    for pid, _, _, est_id, confiabilidad in PROPIETARIOS:
        repositorio.estacionamientos[est_id] = Estacionamiento(
            id=est_id, tipo=TipoEstacionamiento.PRIVADO, propietario_id=pid, confiabilidad=confiabilidad)
    for visita in ("V1", "V2"):
        repositorio.estacionamientos[visita] = Estacionamiento(
            id=visita, tipo=TipoEstacionamiento.VISITA, propietario_id=COMUNIDAD, confiabilidad=1.0)

    for desplazamiento in range(dias):
        dia = (desde + timedelta(days=desplazamiento))
        if dia.weekday() > 4:
            continue
        inicio = dia.replace(hour=8, minute=30, second=0, microsecond=0)
        fin = dia.replace(hour=18, minute=0, second=0, microsecond=0)
        for est_id in PARTICIPANTES:
            for bloque in bloques_entre(inicio, fin):
                if bloque > desde:
                    repositorio.disponibilidad[(est_id, clave_bloque(bloque))] = EstadoBloque.LIBERADO
    repositorio.guardar()


#Cada Propietario y CLiente es una tupla 
#la linea "for pid, nombre, rut, est_id, conf in Propietarios" se encarga de rapartir los valores de cada tupla 
#weekday() devuelve como 0 el Lunes y 6 el Domingo por eso weekday> 4 se refiere a Sabado y Domingo 

