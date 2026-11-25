#En este archivo se sestablece la hora del programa, se hace debido a que el progrema se SIGE usa el tiempo para los arriendos, por lo que aqui establecemos las reglas horarias 

from datetime import datetime, timedelta # Libreria que nos permite trabajar con fechas y horas

#Clase creada par acrear la hora del sistema, al principio parte como si la hora no existira para luego tomar una hora simulada o la hora real del computador o del sistema donde se abra el programa 
class Reloj:
    #Funcion que estblece que la hora simulada es inexistente al inicio hasta que se le indique lo contrario
    def __init__(self):
        self._simulada = None

    #Funcion que devuelve la hora simulada si existe o de lo contrario se usara la hora del sistema, 
    #.replace srive para quitar fracciones y segundos para un hora mas
    def ahora(self):
        if self._simulada is not None:
            return self._simulada
        return datetime.now().replace(second=0, microsecond=0)

    #Funcion que fija una hora simulada para el programa
    def fijar(self, momento):
        self._simulada = momento

    #Esta funcion sume minutos al tiempo del programa y deja la hora fija, siendo esta una hora simulada, con esto el tiempo no sigue corriendo
    def avanzar(self, minutos):
        self._simulada = self.ahora() + timedelta(minutes=minutos) 

    #Funcion que elimina la hora simulada 
    def usar_hora_real(self):
        self._simulada = None

    #Funcion que indica dentro del programa si se esta usando una hora simulada o la hora real del sistema 
    #@property airve para no escribir parentesis y tratar una funcion como dato
    @property
    def es_simulado(self):
        return self._simulada is not None

        