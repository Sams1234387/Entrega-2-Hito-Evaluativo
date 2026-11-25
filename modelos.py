#Archivo que define lo que tiene cada componente o "cosa" del sistema, propietarios, clientes, reservas, estacionamientos, etc

from dataclasses import dataclass, fields
from datetime import datetime, timedelta

#Formatos
FORMATO_FECHA_HORA="%Y-%m-%d %H:%M"
FORMATO_FECHA= "%Y-%m-%d"
FORMATO_HORA= "%H:%M"

#Tipos de estacionamientos que tiene el edificio y que le permitiran al sistema saber cuales puede ofrecer, no puede ofrecer como arriendo uno de visita pero si privado
class TipoEstacionamiento:
    PRIVADO = "PRIVADO"
    VISITA = "VISITA"

#Estado que tienen los bloques de 30 min, no se puede arrendar un bloque de 30 minutos que este bloqeado  
class EstadoBloque:
    LIBERADO= "LIBERADO"
    BLOQUEADO= "BLOQUEADO"

#Aqui se establecen los estados que pueden tener las reservas
class EstadoReserva:
    PENDIENTE= "PENDIENTE"  # Reserva creada pero aún no confirmada por el operdador
    CONFIRMADA= "CONFIRMADA"  # Reserva confirmada por el operador
    CANCELADA= "CANCELADA"    # Reserva se cancelo por distintos motivos, ya sea por el cliente o por el operador  
    LIBERADA= "LIBERADA"      #Reserva liberada por el mismo cliente, ya que este no uso todo el tiempo que habia agendado
    FINALIZADA= "FINALIZADA"      #Se completo el arriendo y se finalizo la reserva
    NO_PRESENTADA= "NO_PRESENTADA" #El cliente no llego

    VIGENTES= (PENDIENTE, CONFIRMADA) #Reservas que aun estan activas y no se han cancelado, liberado o finalizado

#Clase que define los resultados posibles al cerra una reserva 
class Resultado:
    FINALIZADA= "FINALIZADA"      #Se completo el arriendo y se finalizo la reserva
    SOBRETIEMPO= "SOBRETIEMPO" # El cliente se paso del tiempo de arriendo y se le aplico una penalizacion
    NO_PRESENTADA= "NO_PRESENTADA"   #El cliente no llego

COMUNIDAD= "COMUNIDAD"
ADMIN_ID= "ADMIN"

#Clase que define quien esta usandoe el programa
class Destinatario:
    PROPIETARIO= "PROPIETARIO"
    CLIENTE= "CLIENTE"
    ADMINISTRADOR= "ADMINISTRADOR"

#Definimos la clase Propetario
@dataclass
class Propietario:
    id: str
    nombre: str
    rut: str

#Definimos la clase Cliente
@dataclass
class Cliente:
    id: str
    nombre: str
    rut: str
    patente: str

#Definimos la clase Estacionamiento
@dataclass
class Estacionamiento:
    id: str
    tipo: str
    propietario_id: str
    confiabilidad: float    #Confiabilidad del estacionamiento respecto a las posibilidades que el dueño vuelva de imprevisto, entre 0 y 1, siendo 1 el mas confiable y 0 el menos confiable, entre mas alto significa que tiende a seguir la misma rutina
   

#Definimos la clase Reserva y sus montos
@dataclass
class Reserva:
    id: int
    cliente_id: str
    estacionamiento_id: str
    propietario_id: str
    inicio: datetime
    fin: datetime
    estado: str
    monto_total: int
    monto_tarifa: int
    monto_penalizacion: int
    creada_en: datetime
    motivo: str

    #Funcion que calcula cuantos bloques de 30 minutos dura la reserva, se hace para poder calcular el monto de la reserva y el valor que se le cobrara al cliente
    @property
    def bloques(self):
        return int((self.fin - self.inicio).total_seconds() // (30 * 60))  # Calcula la diferencia en segundos y la convierte a bloques de 30 minutos

#Definimos la clase Evento, nna fila del historial: cada cambio relevante queda registrado con fecha, hora, estacionamiento, cliente, estado y monto
@dataclass
class Evento:
    id: int
    momento: datetime
    tipo: str
    reserva_id: str
    estacionamiento_id: str
    propietario_id: str
    cliente_id: str
    fecha: str
    hora_inicio: str
    hora_fin: str
    estado: str
    monto: int
    detalle: str

#DEfinimos la clase Liquidacion, refierondose al monto liquido que le llega a cada actor por la resererva de cada estacionamiento
@dataclass
class Liquidacion:
    reserva_id: int
    momento: datetime
    fecha: str
    estacionamiento_id: str
    propietario_id: str
    monto_tarifa: int
    monto_penalizacion: int
    a_propietario: int
    a_operador: int
    a_administracion: int

#Definimos Notificacion, clase que hace que le llege una notificacion a cada actor, dependiendo de lo que se necesite o solo para dar una iformacion
@dataclass
class Notificacion:
    id: int
    momento: datetime
    destinatario_tipo: str
    destinatario_id: str
    destinatario_nombre: str
    asunto: str
    mensaje: str
    reserva_id: str
    canal: str

#a_fila, funcion que convierte un objeto en un diccionario de texto, listo para escribirlo en un CSV
def a_fila(objeto):
    fila = {}
    for campo in fields(objeto):
        valor = getattr(objeto, campo.name)
        if isinstance(valor, datetime):
            valor = valor.strftime(FORMATO_FECHA_HORA)
        fila[campo.name] = valor
    return fila

#desde_fila, hace lo contrario a la anterior, crea el objeto a partir de una fila leída del CSV
def desde_fila(clase, fila):
    datos = {}
    for campo in fields(clase):
        texto = fila[campo.name]
        if campo.type is datetime:
            datos[campo.name] = datetime.strptime(texto, FORMATO_FECHA_HORA)
        elif campo.type is int:
            datos[campo.name] = int(texto)
        elif campo.type is float:
            datos[campo.name] = float(texto)
        else:
            datos[campo.name] = texto
    return clase(**datos)

#Funcion para identificar cada bloque 
def clave_bloque(momento):
    return momento.strftime(FORMATO_FECHA_HORA)

#Lista el inicio de cada bloque de 30 minutos entre dos horas
def bloques_entre(inicio, fin):
    bloques = []
    actual = inicio
    while actual < fin:
        bloques.append(actual)
        actual += timedelta(minutes=30)
    return bloques


#@dataclass es una clase que guarda datos 
#fields lista los campos de una dataclass, permite escribir "a_fila" y "desde_fila" una sola vez para todas las clases
#strftime y strptime, convierten un datetime en texto y el texto en datetime.
#@property, en Reserva, bloques se calcula al pedirlo ((fin - inicio) dividido en bloques de 30 minutos)