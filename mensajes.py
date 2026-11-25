#Este archivo contiene el codigo de los mensajes o notificaciones que el llegan por la aplicacion a cada uno de los actores, cada función recibe datos del sistema y devuelve una pareja (asunto, mensaje). 
#No toma decisiones ni guarda nada: solo redacta. Está separado de la lógica para que se pueda cambiar la redacción de un aviso sin tocar las reglas. 

from datetime import timedelta

import tarifas

clp = tarifas.clp
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

#Esta funcion da el dia de la semana en que se recibe el mensaje, con un formato de dia, mes y año
def fecha_texto(momento):
    return f"{DIAS[momento.weekday()]} {momento:%d-%m-%Y}"

#Funcion similar a la enterior, pero en ve de indicar el dia de la reserva o de la notificacion, indica la hora con su respectivo formato
def horario(reserva):
    return f"{reserva.inicio:%H:%M} a {reserva.fin:%H:%M}"


#Esta funcion hara que el mensaje o notificacion arme un bloque con los datos o informacion de este, esto con el objetivo que la aplicacion tenga un caracter mas profesional y sea mas ordenada
def _lineas(*pares):
    ancho = max(len(etiqueta) for etiqueta, _ in pares)
    return "\n".join(f"{etiqueta + ':':<{ancho + 1}} {valor}" for etiqueta, valor in pares)

#Las funciones siguientes se centran en las notificaciones que recibe el cliente a la hora de agendar, cancelar o de cualquier otra accion que este tenga dentro de la aplicacion

#Cuando el cliente intente arrendar un estacionamiento
def cliente_solicitud(cliente, r):
    asunto= f"Se recibio su solicitud de reserva #{r.id} con exito "
    mensaje= (f"Hola, cliente {cliente.nombre}, \n\n"
              f"Su solicitud quedo registrada y a la espera de ser asignada." 
              f"Se le informara a la brevedad cuando se le asigne un estacionamiento. \n\n"
              +_lineas(("Reserva", f"#{r.id}"), ("Fecha", fecha_texto(r.inicio)),
                       ("Horario", horario(r)), ("Valor Estimado", clp(r.monto_total))))
    return asunto, mensaje

#Cuando el cliente se le confirme el arriendo
def cliente_arriendo_exitoso(cliente, r, est):
    gratis_hasta = r.inicio - timedelta(minutes=tarifas.CANCELACION_SIN_COSTO_MIN)
    asunto = f"¡Arriendo exitoso! Reserva #{r.id} confirmada en {est.id}"
    mensaje = (f"Hola {cliente.nombre},\n\n"
               f"Su arriendo fue confirmado y el pago quedó registrado. Estos son sus datos:\n\n"
               + _lineas(("Reserva", f"#{r.id}"),
                         ("Estacionamiento", est.id),
                         ("Fecha", fecha_texto(r.inicio)),
                         ("Horario", f"{horario(r)} ({r.bloques} bloques de 30 min)"),
                         ("Patente autorizada", cliente.patente),
                         ("Valor pagado", clp(r.monto_total)))
               + f"\n\nCómo ingresar: presente su patente en portería. Solo pueden entrar los "
                 f"vehículos con patente registrada.\n"
                 f"Importante: Se debe retirar su vehículo a más tardar a las {r.fin:%H:%M}. En caso de "
                 f"pasarse, se cobra {clp(tarifas.PENALIZACION_SOBRETIEMPO_BLOQUE)} por cada "
                 f"30 minutos excedidos.\n"
                 f"Cancelación sin costo hasta las {gratis_hasta:%H:%M} del {gratis_hasta:%d-%m-%Y}.")
    return asunto, mensaje

#Cuando el estacionamiento que se le agendo a un cliente pero llegue el dueño, la notificacion del cambio de estacionamiento es este codigo         
def cliente_reasignada(cliente, r, anterior, nuevo, motivo):
    asunto = f"Cambió su estacionamiento de la reserva #{r.id}, ahora su estacionamiento es: {nuevo}"
    mensaje = (f"Hola {cliente.nombre},\n\n"
               f"Tu reserva sigue confirmada, pero cambió el estacionamiento por: ({motivo}).\n\n"
               + _lineas(("Reserva", f"#{r.id}"), ("Antes", anterior), ("Ahora", nuevo),
                         ("Fecha", fecha_texto(r.inicio)), ("Horario", horario(r)),
                         ("Patente autorizada", cliente.patente))
               + "\n\nNo se debe pagar adicional. Portería ya avisada del cambio.")
    return asunto, mensaje

#Funcion cuando el cliente se le cancele su reserva debido a que el dueño llego
def cliente_cancelada_contingencia(cliente, r, reembolso):
    asunto = f"Tuvimos que cancelar su reserva #{r.id}, lamentamos los inconvenientes"
    mensaje = (f"Hola {cliente.nombre},\n\n"
               f"El propietario necesitó su estacionamiento y no había otro disponible para el  "
               f"horario de usted ({fecha_texto(r.inicio)}, {horario(r)}). Lamentamos el inconveniente.\n\n"
               f"Se le devolvio el 100% de lo pagado: {clp(reembolso)}. No se cobra ninguna penalización.")
    return asunto, mensaje

#Funcion de la notificacion que le llega al cliente a la hora de que el mismo cancele su arriendo
def cliente_cancelacion(cliente, r, penalizacion, reembolso):
    asunto = f"Reserva #{r.id} cancelada"
    detalle = _lineas(("Reserva", f"#{r.id}"), ("Reembolso", clp(reembolso)),
                      ("Penalización", clp(penalizacion)))
    extra = ("" if penalizacion == 0 else
             "\n\nComo se cancelo con menos de 1 hora de anticipación, se retuvo el primer bloque.")
    return asunto, f"Hola {cliente.nombre},\n\nSu cancelación quedó registrada.\n\n{detalle}{extra}"

#Notificacion cuando el cliente no usa todo el tiempo de su reserva
def cliente_liberacion(cliente, r, usados, cobrado, reembolso):
    asunto = f"Reserva #{r.id} terminada antes de tiempo"
    detalle = _lineas(("Reserva", f"#{r.id}"), ("Bloques usados", usados),
                      ("Cobrado", clp(cobrado)), ("Reembolso", clp(reembolso)))
    return asunto, f"Hola {cliente.nombre},\n\nLiberaste tu estacionamiento antes de lo reservado.\n\n{detalle}"


#Esta funcion es de la notificacion cuando se confirma la extension de reserva de un cliente 
def cliente_extension(cliente, r, cobro_extra):
    asunto = f"Reserva #{r.id} extendida hasta las {r.fin:%H:%M}"
    detalle = _lineas(("Reserva", f"#{r.id}"), ("Nuevo horario", horario(r)),
                      ("Cobro adicional", clp(cobro_extra)), ("Valor total", clp(r.monto_total)))
    return asunto, f"Hola {cliente.nombre},\n\nLa extensión fue aceptada.\n\n{detalle}"


#Notifacion cuando un cliente se pase del tiempo maximo, se le cancele la reserva con el cargo de penalizacion
def cliente_cierre(cliente, r, estado_texto):
    asunto = f"Reserva #{r.id} cerrada: {estado_texto}"
    detalle = _lineas(("Reserva", f"#{r.id}"), ("Tarifa", clp(r.monto_tarifa)),
                      ("Penalización", clp(r.monto_penalizacion)))
    return asunto, f"Hola {cliente.nombre},\n\nTu reserva fue cerrada ({estado_texto}).\n\n{detalle}"



#Aqui se ven los mnesajes que le llegan al propietario desde la aplicacion, ya sea para confirmar la liberacion de su estacionamiento o cualuqier accion dentro de la app

# Notificacion que le llega para confirmacion la liberacion de su estacionamiento para que se pueda arrendar
def prop_liberacion(prop, est, inicio, fin, bloques):
    asunto = f"Liberaste tu estacionamiento {est.id}"
    return asunto, (f"Hola {prop.nombre},\n\nTu estacionamiento {est.id} quedó disponible para "
                    f"terceros el {fecha_texto(inicio)} de {inicio:%H:%M} a {fin:%H:%M} "
                    f"({bloques} bloques). Recuerda que siempre puedes bloquearlo si lo necesitas.")


#Cuando un propietario establece una rutina, la app le confirma que se registro con exito y ya no tendra que liberar su estacionamiento de manera manual cuando no este en el edificio 
def prop_recurrente(prop, est, detalle):
    return (f"Tu horario recurrente de {est.id} quedó activo",
            f"Hola {prop.nombre},\n\nAplicamos tu rutina semanal a {est.id}: {detalle}.")


# Cuando un propietario queda bloqueado por orden de su propietario, a este le llega una notifiacion
def prop_bloqueo(prop, est, inicio, fin, afectadas):
    asunto = f"Bloqueaste tu estacionamiento {est.id}"
    texto = (f"Hola {prop.nombre},\n\nTu estacionamiento {est.id} quedó bloqueado el "
             f"{fecha_texto(inicio)} de {inicio:%H:%M} a {fin:%H:%M}. Tienes prioridad sobre tu espacio.")
    if afectadas:
        texto += (f"\n\nHabía {afectadas} reserva(s) afectada(s). Ya fueron reubicadas o canceladas con "
                  f"reembolso; no tienes que hacer nada.")
    return asunto, texto


#Cada vez que se arriende el estacionamiento de un propietario, le llega una notificacion con todos los datos de quien agendo su estacionamiento y en que horario
def prop_reservado(prop, est, r, ingreso_estimado):
    asunto = f"Tu estacionamiento {est.id} fue reservado"
    return asunto, (f"Hola {prop.nombre},\n\nUn cliente externo reservó tu estacionamiento.\n\n"
                    + _lineas(("Reserva", f"#{r.id}"), ("Estacionamiento", est.id),
                              ("Fecha", fecha_texto(r.inicio)), ("Horario", horario(r)),
                              ("Tu ingreso estimado", clp(ingreso_estimado)))
                    + "\n\nEl vehículo debe salir 30 minutos antes de la hora en que declaraste que vuelves.")


#Parecido a la funcion anterior, esta funcion le dara una notificacion al propietario cada vez que un cliente cancele la reserva de su estacionamiento
def prop_reserva_cancelada(prop, est, r, penalizacion):
    asunto = f"Se canceló la reserva #{r.id} de tu estacionamiento {est.id}"
    texto = (f"Hola {prop.nombre},\n\nEl cliente canceló la reserva del {fecha_texto(r.inicio)}, "
             f"{horario(r)}. Tu estacionamiento queda libre.")
    if penalizacion:
        texto += f"\n\nPor cancelación tardía recibes una compensación de {clp(penalizacion)}."
    return asunto, texto


# Cuando una reserva se cambie de estacionamiento por cualquier motivo posible, le llega una notificacion al propietario de que el cliente ya no usara su estacionamiento
def prop_reserva_movida(prop, est, r):
    return (f"La reserva #{r.id} ya no usa tu estacionamiento {est.id}",
            f"Hola {prop.nombre},\n\nLa administración reubicó la reserva #{r.id} "
            f"({fecha_texto(r.inicio)}, {horario(r)}) en otro estacionamiento. {est.id} queda libre.")


#Funcion del mensaje que le llega al propietario cuando un cliente extiende su plazo de reserva en su estacionamiento 
def prop_extension(prop, est, r):
    return (f"Se extendió la reserva #{r.id} en {est.id}",
            f"Hola {prop.nombre},\n\nLa reserva #{r.id} ahora termina a las {r.fin:%H:%M} "
            f"({fecha_texto(r.inicio)}). Tu ingreso aumenta según los bloques agregados.")


#Notificacion del monto liquido recibido para el propietario por el arriendo
def prop_liquidacion(prop, est, r, monto):
    asunto = f"Recibiste {clp(monto)} por la reserva #{r.id}"
    return asunto, (f"Hola {prop.nombre},\n\nSe cerró la reserva #{r.id} de {est.id} "
                    f"({fecha_texto(r.inicio)}, {horario(r)}).\n\n"
                    + _lineas(("Tu parte", clp(monto)), ("Tarifa de la reserva", clp(r.monto_tarifa)),
                              ("Penalizaciones", clp(r.monto_penalizacion))))



#Funciones de las notificaciones que le llegan al operador 

#Funcion del mensaje que le llega al operador cuando un clinete trata de agendar un horario 
def admin_pendiente(cliente, r):
    return (f"Nueva reserva #{r.id} pendiente de asignar",
            f"{cliente.nombre} (patente {cliente.patente}) solicitó {fecha_texto(r.inicio)}, "
            f"{horario(r)}, valor {clp(r.monto_total)}. Falta asignarle un estacionamiento.")


#Mensaje que llega cuando un dueño bloquea su espacio, no hay estacionamientos libres y debe de cancelar el arriendo
def admin_contingencia(prop, est, r, cliente, accion, destino):
    asunto = f"Contingencia en {est.id}: el propietario recuperó su espacio"
    if accion == "REASIGNADA":
        texto = (f"{prop.nombre} bloqueó {est.id}. La reserva #{r.id} ({horario(r)}) se reubicó en "
                 f"{destino}. Avisar a portería: patente {cliente.patente}.")
    else:
        texto = (f"{prop.nombre} bloqueó {est.id} y no había estacionamientos de visita libres. "
                 f"La reserva #{r.id} ({horario(r)}) se canceló con reembolso total.")
    return asunto, texto


#Mensaje cuando un cliente cancela por su cuenta el arriendo
def admin_cancelacion(cliente, r):
    return (f"Reserva #{r.id} cancelada por el cliente",
            f"{cliente.nombre} canceló la reserva #{r.id} ({fecha_texto(r.inicio)}, {horario(r)}). "
            f"El estacionamiento {r.estacionamiento_id or '(sin asignar)'} queda libre.")


#Cliente no usa todo el tiempo de arriendo
def admin_liberacion(cliente, r):
    return (f"Reserva #{r.id} liberada antes de tiempo",
            f"{cliente.nombre} terminó antes. {r.estacionamiento_id} queda libre desde las {r.fin:%H:%M}.")


#El cliente se le debe cancelar el arriendo y cobrar penalizacion
def admin_cierre(cliente, r, estado_texto):
    return (f"Reserva #{r.id} cerrada: {estado_texto}",
            f"{cliente.nombre}: tarifa {clp(r.monto_tarifa)}, penalización {clp(r.monto_penalizacion)}.")

#Return asunto, mensaje devuelve dos valores a la vez
#*pares es una funcion que acpeta cualquier cantidad de argumentos 
#f-strings de varias lineas son textos armados al insertar datos con {}
#max() y :<10 se usan en _lineas para linear el texto


