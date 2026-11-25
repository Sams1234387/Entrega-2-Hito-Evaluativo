#Aqui se establacen las reglas del negocio: Precios, tope, plazos, porcentajes, etc
#Si una regla del negocio se debe de cambiar, debe ser dentro de este archivo y se cambiara para todo el resto de nuestro programa 

#Se usan los bloques de 30n minutos que vienen eln el dataset original, ademas de los precios que establecimos en la entrega uno, 900$ por cada bloque de media hora, con un maximo de arriendo de 12000$ por dia 
MINUTOS_BLOQUE = 30
TARIFA_BLOQUE = 900
TOPE_DIARIO = 12000

#Plazos de tiempo que establecimos en la primera entrega, situaciones donde el cliente o no llega o se pasa del tiempo, etc
ANTICIPACION_MINIMA_MIN= 30
CANCELACION_SIN_COSTO_MIN= 60
ESPERA_NO_SHOW_MIN = 20
PORCENTAJE_NO_SHOW= 0.50
PENALIZACION_SOBRETIEMPO_BLOQUE = 2700

#Porcentajes de como se reparten las ganacias en nuestros actores, propietarios 70%, operadores 20% y edificio 10%, esto siendo porcentajes que se establecieron en las primera entrega, pero se debe a que los propietarios son los que deben de tener el mayor beneficio, luego los operadores de sige, y por ultimo el edificio o administracion se deben de llevar la parte mas baja
PORCENTAJE_PROPIETARIO = 0.70
PORCENTAJE_OPERADOR = 0.20
PORCENTAJE_ADMINISTRACION = 0.10

#Forma de como se calcvula el valor del arriendo, multiplica los bloques por la tarifa, pero nunca pasa del tope
def calcular_monto(bloques):
    return min(bloques * TARIFA_BLOQUE, TOPE_DIARIO)

#Como se reparte el dineros luego de calular el monto de cada arriendo 
def repartir(monto):
    propietario = int(round(monto* PORCENTAJE_PROPIETARIO))
    operador = int(round(monto* PORCENTAJE_OPERADOR))
    administracion = monto - propietario - operador   #Se hizo asi por que una razon matematica, como hay redondeos, esta suma da exactamente el monto sin perdidas monetarias
    return propietario, operador, administracion

#Esta funcion se hace para que los numeros que den en las funciones anteriores se pasen a un formate de pesos, es mas que nada una funcion para que el programa sea mucho mas atractivo viualmente y se mas facil trabajar los numeros

def clp(valor):
    return "$" + f"{int(valor):,}".replace(",", ".")