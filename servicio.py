#Este Archivo es el cerebro de todo el programa, aqui estan todas las reglas del negocio, las 6 funcionalidades
#Este archivo es el que determina que se puede o no hacer con el programa

from datetime import timedelta
from math import ceil

import mensajes
import tarifas
from modelos import (ADMIN_ID, Cliente, Destinatario, EstadoBloque, EstadoReserva, Evento,
                     Liquidacion, Notificacion, Reserva, Resultado, TipoEstacionamiento,
                     FORMATO_FECHA, FORMATO_HORA, bloques_entre, clave_bloque)


#Clase que lanza unerror cuando un regla se rompe     
class ReglaNegocioError(Exception):
    pass


#Clase que vera todo el sistema de sige, dentro de ella se modelan las funciones de las reglas del servicio que hacen que todo el programa funcione
class ServicioSIGE:
    #Funcion que recibe los datos del repositorio y el archivo reloj
    def __init__(self, repositorio, reloj):
        self.repo = repositorio
        self.reloj = reloj

    #Funcion que se encarga de buscar a un propietario, en caso de que este no exista mandara un error de que ese propietario no existe
    def _propietario(self, propietario_id):
        if propietario_id not in self.repo.propietarios:
            raise ReglaNegocioError(f"No existe el propietario {propietario_id}.")
        return self.repo.propietarios[propietario_id]

    #Funcion que buscara a un cliente especificio y en caso de no exisitir marcara un error de que ese cliente no esta resgistrado
    def _cliente(self, cliente_id):
        if cliente_id not in self.repo.clientes:
            raise ReglaNegocioError(f"No existe el cliente {cliente_id}.")
        return self.repo.clientes[cliente_id]

    #Funcion que busca un estacionamiento especifico, si no esta lanza un error indicando que tal estacionamineto no existe
    def _estacionamiento(self, estacionamiento_id):
        if estacionamiento_id not in self.repo.estacionamientos:
            raise ReglaNegocioError(f"No existe el estacionamiento {estacionamiento_id}.")
        return self.repo.estacionamientos[estacionamiento_id]

    #Busca una reserva en especifico en la lista de reservas, en caso de no existir el sistema lo indicara 
    def _reserva(self, reserva_id):
        if reserva_id not in self.repo.reservas:
            raise ReglaNegocioError(f"No existe la reserva #{reserva_id}.")
        return self.repo.reservas[reserva_id]

    #Esta funcion es la encargada de ajustar reglas horarias a la hora de buscar un horario en el sistema 
    @staticmethod
    def _validar_periodo(inicio, fin):
        for momento in (inicio, fin):
            if momento.minute not in (0, 30) or momento.second != 0:
                raise ReglaNegocioError(
                    "Las horas deben ser en bloques de 30 minutos (por ejemplo 09:00 o 09:30).") # Si se indica un horario que no sea :00 o :30 se indicara error, ya que los bloques de tiempo del sistema estan medidos asi
        if fin <= inicio:
            raise ReglaNegocioError("La hora de término debe ser posterior a la de inicio.") # Si el usuario ingresa una hora de termino posterior a la del incio el sistema no lo permitira y marcara error 
        if fin.date() != inicio.date():
            raise ReglaNegocioError("El período debe estar dentro de un mismo día.")#Un usuario no puede agendar un hora de inicio en un dia y la de termino a otro dia, las horas debe ser dentro del mismo dia 

    #Esta funcion determina el estado de los bloques de media hora del sistema, se buscan por estacionaminto dentro de las horas limites establecidas, los estados de los bloques indicaran si esta bloqueado, liberado o sin ningun estado
    def _estado_bloque(self, estacionamiento_id, momento):
        return self.repo.disponibilidad.get((estacionamiento_id, clave_bloque(momento)))

    #Esta funcion aplica la regla de no superpocision, rechazara una reserva que tope con otra 
    def _reserva_que_choca(self, estacionamiento_id, inicio, fin, ignorar_id=None):
        for r in self.repo.reservas.values():
            #Si se detecta que entre la hora de incio y termino de una reserva tiene un tope con la hora de inicio y final de otra reserva aun sin tener los mismos horarios, ej: 10:00-12:00 y 11:00 a 13:00 se detecta un tope  
            if (r.estado == EstadoReserva.CONFIRMADA and r.estacionamiento_id == estacionamiento_id
                    and r.id != ignorar_id and r.inicio < fin and inicio < r.fin):
                return r
        return None

    # Esta funcion es la mas importante, dice por qué un estacionamiento no sirve para un horario, o devuelve None si sirve. Revisa cada bloque (liberado, no bloqueado), el colchón (el bloque siguiente al término también debe estar liberado) y que no choque con otra reserva
    def _motivo_incompatibilidad(self, est, inicio, fin, ignorar_id=None, permitir_visita=False):
        if est.tipo == TipoEstacionamiento.VISITA:
            if not permitir_visita:
                return "es un estacionamiento de visita (solo se usa en contingencias)"
        else:
            for bloque in bloques_entre(inicio, fin):
                estado = self._estado_bloque(est.id, bloque)
                if estado == EstadoBloque.BLOQUEADO:
                    return f"el propietario lo bloqueó a las {bloque:{FORMATO_HORA}}"
                if estado != EstadoBloque.LIBERADO:
                    return f"el propietario no lo liberó a las {bloque:{FORMATO_HORA}}"
            #El bloque de 30 minutos despues del termino del horario establecido debe de estar liberado, debido a que es un colchon que se establecio para evitar que a la hora punta de llegada de los propietarios alguno pueda encontrar con su estacionamiento ocupado, por eso se dio unos 30 minutos antes de esa hora para que no hayan posibilidades de que esto pase
            if self._estado_bloque(est.id, fin) != EstadoBloque.LIBERADO:
                return (f"no queda el colchón de 30 min antes de que el propietario regrese "
                        f"(a las {fin:{FORMATO_HORA}})")
        choque = self._reserva_que_choca(est.id, inicio, fin, ignorar_id)
        if choque:
            return (f"ya está asignado a la reserva #{choque.id} "
                    f"({choque.inicio:{FORMATO_HORA}} a {choque.fin:{FORMATO_HORA}})")
        return None

    #Se filtra los estacioamientos para ver cuales sirven y se ordenan por confiabilidad, eso debido a que gracias a esto, se puede saber cual es el mejor estacionamiento, ya que entre mas confiabilidad, hay menos posibilidades de que el dueño tenga un cambio de rutina y llegue sin avisar
    def estacionamientos_compatibles(self, inicio, fin, ignorar_id=None):
        compatibles = [e for e in self.repo.estacionamientos.values()
                       if e.tipo == TipoEstacionamiento.PRIVADO
                       and self._motivo_incompatibilidad(e, inicio, fin, ignorar_id) is None]
        return sorted(compatibles, key=lambda e: (-e.confiabilidad, e.id))

    #Esta funcion es el historial, es todo lo que pase con Sige, se registra, se guarda y se mantienen para un futuro en el Dashboard
    def _registrar(self, tipo, reserva=None, estacionamiento_id="", propietario_id="",
                   cliente_id="", inicio=None, fin=None, estado="", monto=0, detalle=""):
        if reserva is not None:
            estacionamiento_id = reserva.estacionamiento_id
            propietario_id = reserva.propietario_id
            cliente_id = reserva.cliente_id
            inicio, fin, estado = reserva.inicio, reserva.fin, reserva.estado
        evento = Evento(
            id=self.repo.siguiente_id_evento(),
            momento=self.reloj.ahora(),
            tipo=tipo,
            reserva_id=str(reserva.id) if reserva is not None else "",
            estacionamiento_id=estacionamiento_id,
            propietario_id=propietario_id,
            cliente_id=cliente_id,
            fecha=inicio.strftime(FORMATO_FECHA) if inicio else "",
            hora_inicio=inicio.strftime(FORMATO_HORA) if inicio else "",
            hora_fin=fin.strftime(FORMATO_HORA) if fin else "",
            estado=estado,
            monto=int(monto),
            detalle=detalle,
        )
        self.repo.historial.append(evento)

    # Esta funcion crea la notificacion, y la guarda 
    def _enviar(self, tipo, destinatario_id, nombre, texto, reserva=None):
        asunto, mensaje = texto
        self.repo.notificaciones.append(Notificacion(
            id=self.repo.siguiente_id_notificacion(), momento=self.reloj.ahora(),
            destinatario_tipo=tipo, destinatario_id=destinatario_id, destinatario_nombre=nombre,
            asunto=asunto, mensaje=mensaje, reserva_id=str(reserva.id) if reserva else "",
            canal="APP"))

    # Crea la notificacion orientada al cliente 
    def _avisar_cliente(self, cliente, texto, reserva=None):
        self._enviar(Destinatario.CLIENTE, cliente.id, cliente.nombre, texto, reserva)

    # Notificacion orientada a los propietarios 
    def _avisar_propietario(self, propietario_id, texto, reserva=None):
        propietario = self.repo.propietarios.get(propietario_id)
        if propietario is not None:
            self._enviar(Destinatario.PROPIETARIO, propietario.id, propietario.nombre, texto, reserva)

    # Notificacion orientada al operador 
    def _avisar_admin(self, texto, reserva=None):
        self._enviar(Destinatario.ADMINISTRADOR, ADMIN_ID, "Administración", texto, reserva)

    # Se reparte el dinero de manera 70% al propietario, 20% al operador y 10% edificio, las penalizaciones por un tema de que sea atractivo para el dueño, Sige le da el 100% de la penalizaciones al dueño, 
    def _liquidar(self, reserva, avisar_propietario=True):
        if reserva.monto_tarifa == 0 and reserva.monto_penalizacion == 0:
            return
        if any(l.reserva_id == reserva.id for l in self.repo.liquidaciones):
            return
        propietario, operador, administracion = tarifas.repartir(reserva.monto_tarifa)
        if avisar_propietario:
            est = self.repo.estacionamientos.get(reserva.estacionamiento_id)
            dueno = self.repo.propietarios.get(reserva.propietario_id)
            if est and dueno:
                self._avisar_propietario(dueno.id, mensajes.prop_liquidacion(
                    dueno, est, reserva, propietario + reserva.monto_penalizacion), reserva)
        self.repo.liquidaciones.append(Liquidacion(
            reserva_id=reserva.id,
            momento=self.reloj.ahora(),
            fecha=reserva.inicio.strftime(FORMATO_FECHA),
            estacionamiento_id=reserva.estacionamiento_id,
            propietario_id=reserva.propietario_id,
            monto_tarifa=reserva.monto_tarifa,
            monto_penalizacion=reserva.monto_penalizacion,
            
            a_propietario=propietario + reserva.monto_penalizacion,
            a_operador=operador,
            a_administracion=administracion,
        ))

    #El propietario libera su estacionamiento, valida que ese sea su estacionamiento, valida el periodo el tiempo en que liberara su estacionamiento, los bloques durante el periodo liberado se marcan como LIBERADO
    def liberar_estacionamiento(self, propietario_id, estacionamiento_id, inicio, fin):
        self._propietario(propietario_id)
        est = self._estacionamiento(estacionamiento_id)
        if est.tipo != TipoEstacionamiento.PRIVADO or est.propietario_id != propietario_id:
            raise ReglaNegocioError("Ese estacionamiento no pertenece a este propietario.")
        self._validar_periodo(inicio, fin)
        if fin <= self.reloj.ahora():
            raise ReglaNegocioError("Ese período ya terminó; solo se puede liberar tiempo futuro.")

        bloques = bloques_entre(inicio, fin)
        for bloque in bloques:
            self.repo.disponibilidad[(est.id, clave_bloque(bloque))] = EstadoBloque.LIBERADO
        self._registrar("LIBERACION", estacionamiento_id=est.id, propietario_id=propietario_id,
                        inicio=inicio, fin=fin, estado=EstadoBloque.LIBERADO,
                        detalle=f"{len(bloques)} bloques liberados")
        self._avisar_propietario(propietario_id, mensajes.prop_liberacion(
            self.repo.propietarios[propietario_id], est, inicio, fin, len(bloques)))
        self.repo.guardar()
        return len(bloques)

    #La funcion permite que el propietario bloque su estacionamiento, esto en caso de que vaya a ocuaprlo durante el dia, el propietario tiene la preferencia asi que en caso que hayan reservas, se iran a los estacionamientos de visita, encaso de que no se pueda las reservas se cancelaran directamente
    def bloquear_estacionamiento(self, propietario_id, estacionamiento_id, inicio, fin, motivo=""):
        self._propietario(propietario_id)
        est = self._estacionamiento(estacionamiento_id)
        if est.tipo != TipoEstacionamiento.PRIVADO or est.propietario_id != propietario_id:
            raise ReglaNegocioError("Ese estacionamiento no pertenece a este propietario.")
        self._validar_periodo(inicio, fin)
        if fin <= self.reloj.ahora():
            raise ReglaNegocioError("Ese período ya terminó; solo se puede bloquear tiempo futuro.")

        for bloque in bloques_entre(inicio, fin):
            self.repo.disponibilidad[(est.id, clave_bloque(bloque))] = EstadoBloque.BLOQUEADO
        self._registrar("BLOQUEO", estacionamiento_id=est.id, propietario_id=propietario_id,
                        inicio=inicio, fin=fin, estado=EstadoBloque.BLOQUEADO,
                        detalle=motivo or "bloqueo del propietario")

        
        margen = timedelta(minutes=tarifas.MINUTOS_BLOQUE)
        afectadas = sorted((r for r in self.repo.reservas.values()
                            if r.estado == EstadoReserva.CONFIRMADA
                            and r.estacionamiento_id == est.id
                            and r.inicio < fin and inicio < r.fin + margen),
                           key=lambda r: r.inicio)

        resultados = []
        propietario = self.repo.propietarios[propietario_id]
        for reserva in afectadas:
            cliente = self.repo.clientes[reserva.cliente_id]
            #Se intenta reubicar en un estacionamiento de visita; si no hay, se cancela con reembolso.
            visita = self._buscar_visita(reserva)
            if visita is not None:
                anterior = reserva.estacionamiento_id
                reserva.estacionamiento_id = visita.id
                reserva.propietario_id = visita.propietario_id
                reserva.motivo = "contingencia: el propietario recuperó su estacionamiento"
                self._registrar("REASIGNACION", reserva=reserva, monto=0,
                                detalle=f"{anterior} -> {visita.id} (contingencia del propietario)")
                resultados.append({"reserva": reserva.id, "accion": "REASIGNADA",
                                   "destino": visita.id, "reembolso": 0})
                self._avisar_cliente(cliente, mensajes.cliente_reasignada(
                    cliente, reserva, anterior, visita.id, "el propietario recuperó su estacionamiento"), reserva)
                self._avisar_admin(mensajes.admin_contingencia(
                    propietario, est, reserva, cliente, "REASIGNADA", visita.id), reserva)
            else:
                reembolso = reserva.monto_tarifa
                reserva.estado = EstadoReserva.CANCELADA
                reserva.monto_tarifa = 0
                reserva.motivo = "contingencia: el propietario recuperó su estacionamiento"
                self._registrar("CANCELACION", reserva=reserva, monto=0,
                                detalle="cancelada por contingencia del propietario, sin cobro")
                self._registrar("REEMBOLSO", reserva=reserva, monto=reembolso,
                                detalle="reembolso del 100% por contingencia")
                resultados.append({"reserva": reserva.id, "accion": "CANCELADA",
                                   "destino": "", "reembolso": reembolso})
                self._avisar_cliente(cliente, mensajes.cliente_cancelada_contingencia(
                    cliente, reserva, reembolso), reserva)
                self._avisar_admin(mensajes.admin_contingencia(
                    propietario, est, reserva, cliente, "CANCELADA", ""), reserva)
        self._avisar_propietario(propietario_id, mensajes.prop_bloqueo(
            propietario, est, inicio, fin, len(afectadas)))
        self.repo.guardar()
        return resultados

    #Esta funcion busca un estacionamiento libre de visitas para un reserva afectada, esto para intentar no cancelarla
    def _buscar_visita(self, reserva):
        visitas = sorted((e for e in self.repo.estacionamientos.values()
                          if e.tipo == TipoEstacionamiento.VISITA), key=lambda e: e.id)
        for visita in visitas:
            if self._motivo_incompatibilidad(visita, reserva.inicio, reserva.fin,
                                             ignorar_id=reserva.id, permitir_visita=True) is None:
                return visita
        return None

    #La rutina semanal: libera los días y horas indicados durante varias semanas, respetando los bloques que el propietario ya bloqueó y sin liberar tiempo pasado
    def definir_horario_recurrente(self, propietario_id, estacionamiento_id, dias_semana,
                                   hora_inicio, hora_fin, semanas=2):
        self._propietario(propietario_id)
        est = self._estacionamiento(estacionamiento_id)
        if est.tipo != TipoEstacionamiento.PRIVADO or est.propietario_id != propietario_id:
            raise ReglaNegocioError("Ese estacionamiento no pertenece a este propietario.")
        if not dias_semana:
            raise ReglaNegocioError("Debes indicar al menos un día de la semana.")
        if any(d < 0 or d > 6 for d in dias_semana):
            raise ReglaNegocioError("Los días deben ir de 0 (lunes) a 6 (domingo).")
        if semanas < 1 or semanas > 8:
            raise ReglaNegocioError("La rutina puede aplicarse entre 1 y 8 semanas.")

        ahora = self.reloj.ahora()
        liberados, respetados = 0, 0
        for desplazamiento in range(semanas * 7):
            dia = (ahora + timedelta(days=desplazamiento)).date()
            if dia.weekday() not in dias_semana:
                continue
            inicio = ahora.replace(year=dia.year, month=dia.month, day=dia.day,
                                   hour=hora_inicio.hour, minute=hora_inicio.minute,
                                   second=0, microsecond=0)
            fin = inicio.replace(hour=hora_fin.hour, minute=hora_fin.minute)
            self._validar_periodo(inicio, fin)
            for bloque in bloques_entre(inicio, fin):
                if bloque <= ahora:
                    continue
                clave = (est.id, clave_bloque(bloque))
                if self.repo.disponibilidad.get(clave) == EstadoBloque.BLOQUEADO:
                    respetados += 1
                    continue
                self.repo.disponibilidad[clave] = EstadoBloque.LIBERADO
                liberados += 1
        nombres = "LMXJVSD"
        dias_texto = "".join(nombres[d] for d in sorted(dias_semana))
        detalle = (f"días {dias_texto} de {hora_inicio:{FORMATO_HORA}} a "
                   f"{hora_fin:{FORMATO_HORA}}, {semanas} semana(s): "
                   f"{liberados} bloques liberados, {respetados} bloqueos respetados")
        self._registrar("HORARIO_RECURRENTE", estacionamiento_id=est.id,
                        propietario_id=propietario_id, detalle=detalle)
        self._avisar_propietario(propietario_id, mensajes.prop_recurrente(
            self.repo.propietarios[propietario_id], est, detalle))
        self.repo.guardar()
        return liberados, respetados

    #Se registra al cliente con nombre, RUT y patente, en caso que falte un dato no se permitira el resgistro, al igual que no se permitira si ya esta el rut registrada 
    def registrar_cliente(self, nombre, rut, patente):
        nombre, rut, patente = nombre.strip(), rut.strip(), patente.strip().upper()
        if not nombre or not rut or not patente:
            raise ReglaNegocioError("Nombre, RUT y patente son obligatorios.")
        if any(c.rut == rut for c in self.repo.clientes.values()):
            raise ReglaNegocioError("Ya existe un cliente registrado con ese RUT.")
        cliente = Cliente(id=self.repo.siguiente_id_cliente(), nombre=nombre, rut=rut, patente=patente)
        self.repo.clientes[cliente.id] = cliente
        self.repo.guardar()
        return cliente

    # Valida el período, la anticipación mínima de 30 minutos, que el cliente no tenga otra reserva en ese horario y que exista al menos un estacionamiento compatible. Crea la reserva PENDIENTE con su valor, y avisa al cliente y al administrador
    def crear_reserva(self, cliente_id, inicio, fin):
        cliente = self._cliente(cliente_id)
        self._validar_periodo(inicio, fin)
        ahora = self.reloj.ahora()
        minimo = ahora + timedelta(minutes=tarifas.ANTICIPACION_MINIMA_MIN)
        if inicio < minimo:
            raise ReglaNegocioError(
                f"La reserva requiere al menos {tarifas.ANTICIPACION_MINIMA_MIN} minutos de "
                f"anticipación (hora mínima de inicio: {minimo:{FORMATO_HORA}}).")
        for otra in self.repo.reservas.values():
            if (otra.cliente_id == cliente_id and otra.estado in EstadoReserva.VIGENTES
                    and otra.inicio < fin and inicio < otra.fin):
                raise ReglaNegocioError(
                    f"El cliente ya tiene la reserva #{otra.id} en ese horario.")
        if not self.estacionamientos_compatibles(inicio, fin):
            raise ReglaNegocioError("No hay estacionamientos disponibles para ese horario.")

        bloques = len(bloques_entre(inicio, fin))
        reserva = Reserva(
            id=self.repo.siguiente_id_reserva(), cliente_id=cliente_id, estacionamiento_id="",
            propietario_id="", inicio=inicio, fin=fin, estado=EstadoReserva.PENDIENTE,
            monto_total=tarifas.calcular_monto(bloques), monto_tarifa=0, monto_penalizacion=0,
            creada_en=ahora, motivo="")
        self.repo.reservas[reserva.id] = reserva
        self._registrar("RESERVA_CREADA", reserva=reserva, monto=reserva.monto_total,
                        detalle=f"{bloques} bloques, valor {tarifas.clp(reserva.monto_total)}")
        self._avisar_cliente(cliente, mensajes.cliente_solicitud(cliente, reserva), reserva)
        self._avisar_admin(mensajes.admin_pendiente(cliente, reserva), reserva)
        self.repo.guardar()
        return reserva

    # Si la reserva esta pendiente y el cliente quiere cancelar no se le ocbrara, en caso que este confirmada con mas de 60 minutos tampoco se le cobra, en caso de cancelar con menos de 60 minutos se le descuenta el primer bloque de tiempo
    def cancelar_reserva(self, cliente_id, reserva_id):
        reserva = self._reserva(reserva_id)
        if reserva.cliente_id != cliente_id:
            raise ReglaNegocioError("Esa reserva no pertenece a este cliente.")
        if reserva.estado not in EstadoReserva.VIGENTES:
            raise ReglaNegocioError(f"La reserva #{reserva.id} ya está {reserva.estado}.")
        ahora = self.reloj.ahora()
        if ahora >= reserva.inicio:
            raise ReglaNegocioError(
                "La reserva ya comenzó: usa 'liberar reserva' para terminarla anticipadamente.")

        penalizacion, reembolso = 0, 0
        era_confirmada = reserva.estado == EstadoReserva.CONFIRMADA
        if reserva.estado == EstadoReserva.CONFIRMADA:
            anticipacion = reserva.inicio - ahora
            #Si falta menos de una hora se le cobra el primer bloque de tiempo 
            if anticipacion < timedelta(minutes=tarifas.CANCELACION_SIN_COSTO_MIN):
                penalizacion = tarifas.TARIFA_BLOQUE
            reembolso = reserva.monto_tarifa - penalizacion

        reserva.estado = EstadoReserva.CANCELADA
        reserva.monto_tarifa = 0
        reserva.monto_penalizacion = penalizacion
        reserva.motivo = "cancelada por el cliente"
        self._registrar("CANCELACION", reserva=reserva, monto=penalizacion,
                        detalle=("sin costo" if penalizacion == 0 else
                                 f"cancelación tardía: se retiene 1 bloque ({tarifas.clp(penalizacion)})"))
        if reembolso > 0:
            self._registrar("REEMBOLSO", reserva=reserva, monto=reembolso, detalle="reembolso al cliente")
        self._liquidar(reserva, avisar_propietario=False)
        cliente = self.repo.clientes[reserva.cliente_id]
        self._avisar_cliente(cliente, mensajes.cliente_cancelacion(cliente, reserva, penalizacion, reembolso), reserva)
        dueno = self.repo.propietarios.get(reserva.propietario_id)
        est = self.repo.estacionamientos.get(reserva.estacionamiento_id)
        if era_confirmada and dueno and est:
            self._avisar_propietario(dueno.id, mensajes.prop_reserva_cancelada(
                dueno, est, reserva, penalizacion), reserva)
        self._avisar_admin(mensajes.admin_cancelacion(cliente, reserva), reserva)
        self.repo.guardar()
        return {"penalizacion": penalizacion, "reembolso": reembolso}

    # Esta funcion hace que cuando el cliente no use todo el tiempo reservado, se cobran los bloques usados, redondeando hacia arriba, minimo se le cobrara uno, y los demas quedaran liberados y se le reembolsara los bloques no usados
    def liberar_reserva(self, cliente_id, reserva_id):
        reserva = self._reserva(reserva_id)
        if reserva.cliente_id != cliente_id:
            raise ReglaNegocioError("Esa reserva no pertenece a este cliente.")
        if reserva.estado != EstadoReserva.CONFIRMADA:
            raise ReglaNegocioError(f"Solo se puede liberar una reserva CONFIRMADA, está {reserva.estado}.")
        ahora = self.reloj.ahora()
        if ahora < reserva.inicio:
            raise ReglaNegocioError("La reserva aún no comienza: usa 'cancelar reserva'.")
        if ahora >= reserva.fin:
            raise ReglaNegocioError("La reserva ya terminó.")

        #Se le redondea hacia arriba los bloques usados ya que igual uso parte del bloque, y se cobra minimo un bloque para que los demas actores, propietario, operador y edificio tengan un beneficio seguro por reserva 
        usados = max(1, ceil((ahora - reserva.inicio).total_seconds() / 60 / tarifas.MINUTOS_BLOQUE))
        usados = min(usados, reserva.bloques)
        monto_usado = tarifas.calcular_monto(usados)
        reembolso = reserva.monto_tarifa - monto_usado
        fin_original = reserva.fin

        reserva.fin = reserva.inicio + timedelta(minutes=usados * tarifas.MINUTOS_BLOQUE)
        reserva.monto_total = monto_usado
        reserva.monto_tarifa = monto_usado
        reserva.estado = EstadoReserva.LIBERADA
        reserva.motivo = "liberada anticipadamente por el cliente"
        self._registrar("LIBERACION_RESERVA", reserva=reserva, monto=monto_usado,
                        detalle=f"usó {usados} bloque(s) de {int((fin_original - reserva.inicio).total_seconds() // 1800)}")
        if reembolso > 0:
            self._registrar("REEMBOLSO", reserva=reserva, monto=reembolso,
                            detalle="reembolso de los bloques no usados")
        self._liquidar(reserva)
        cliente = self.repo.clientes[reserva.cliente_id]
        self._avisar_cliente(cliente, mensajes.cliente_liberacion(cliente, reserva, usados, monto_usado, reembolso), reserva)
        self._avisar_admin(mensajes.admin_liberacion(cliente, reserva), reserva)
        self.repo.guardar()
        return {"bloques_usados": usados, "cobrado": monto_usado, "reembolso": reembolso}

    #Con esta funcion el cliente puede extender su plazo de reserva, alias obtener mas bloques de timepo, esto se hace tendiendo en concideracion topes de horario, el tiempo maximo del estacionamiento, el tope de horario se tiene en consideracion en el cobro final
    def extender_reserva(self, cliente_id, reserva_id, bloques_extra):
        reserva = self._reserva(reserva_id)
        if reserva.cliente_id != cliente_id:
            raise ReglaNegocioError("Esa reserva no pertenece a este cliente.")
        if reserva.estado != EstadoReserva.CONFIRMADA:
            raise ReglaNegocioError("Solo se puede extender una reserva CONFIRMADA.")
        if bloques_extra < 1 or bloques_extra > 8:
            raise ReglaNegocioError("Puedes extender entre 1 y 8 bloques de 30 minutos.")
        ahora = self.reloj.ahora()
        if ahora >= reserva.fin:
            raise ReglaNegocioError("La reserva ya terminó; no se puede extender.")

        nuevo_fin = reserva.fin + timedelta(minutes=bloques_extra * tarifas.MINUTOS_BLOQUE)
        self._validar_periodo(reserva.inicio, nuevo_fin)
        est = self._estacionamiento(reserva.estacionamiento_id)
        #Se utiliza la misma revision de horarios que el reservar por primera vez, esto para que sea mas simple la tarea de extender el plazo 
        motivo = self._motivo_incompatibilidad(est, reserva.inicio, nuevo_fin,
                                               ignorar_id=reserva.id, permitir_visita=True)
        if motivo:
            raise ReglaNegocioError(f"No se puede extender: {motivo}.")

        nuevo_total = tarifas.calcular_monto(reserva.bloques + bloques_extra)
        cobro_extra = nuevo_total - reserva.monto_total
        fin_anterior = reserva.fin
        reserva.fin = nuevo_fin
        reserva.monto_total = nuevo_total
        reserva.monto_tarifa += cobro_extra
        reserva.motivo = "extendida por el cliente"
        self._registrar("EXTENSION", reserva=reserva, monto=cobro_extra,
                        detalle=(f"término {fin_anterior:{FORMATO_HORA}} -> {nuevo_fin:{FORMATO_HORA}}"
                                 + (" (tope diario alcanzado)" if cobro_extra < bloques_extra * tarifas.TARIFA_BLOQUE else "")))
        cliente = self.repo.clientes[reserva.cliente_id]
        self._avisar_cliente(cliente, mensajes.cliente_extension(cliente, reserva, cobro_extra), reserva)
        dueno = self.repo.propietarios.get(reserva.propietario_id)
        if dueno:
            self._avisar_propietario(dueno.id, mensajes.prop_extension(dueno, est, reserva), reserva)
        self.repo.guardar()
        return cobro_extra

    #Esta funcion pasa una reserva de PENDIENTE a CONFIRMADA,  si no se indica estacionamiento, elige el más confiable de los compatibles; si se indica, valida que sirva, aquí se cobra el prepago, avisa al cliente y al propietario 
    def asignar_reserva(self, reserva_id, estacionamiento_id=None):
        reserva = self._reserva(reserva_id)
        if reserva.estado != EstadoReserva.PENDIENTE:
            raise ReglaNegocioError(f"Solo se asignan reservas PENDIENTES (esta está {reserva.estado}).")
        if reserva.inicio <= self.reloj.ahora():
            raise ReglaNegocioError("La reserva ya comenzó o venció; no se puede asignar.")

        if estacionamiento_id is None:
            candidatos = self.estacionamientos_compatibles(reserva.inicio, reserva.fin)
            if not candidatos:
                raise ReglaNegocioError("Ya no hay estacionamientos compatibles para esta reserva.")
            #Se elige el estacioanimento con mayor confiabilidad para evitar que se tenga que cancelar la reserva por que el dueño vuelva
            elegido = candidatos[0]
        else:
            elegido = self._estacionamiento(estacionamiento_id)
            motivo = self._motivo_incompatibilidad(elegido, reserva.inicio, reserva.fin)
            if motivo:
                raise ReglaNegocioError(f"{elegido.id} no es compatible: {motivo}.")

        reserva.estacionamiento_id = elegido.id
        reserva.propietario_id = elegido.propietario_id
        reserva.estado = EstadoReserva.CONFIRMADA
        #El prepago se cobra recien al asignar debido a que recien en este momento la reserva se confirma, en casode cobrarlo en la reservacion se le cobraria al cliente aun con la posibilidad de no haber estacionamientos, y tener que reembolsar, por esto se cobra en la asignacion 
        reserva.monto_tarifa = reserva.monto_total
        reserva.motivo = "asignada por el administrador"
        self._registrar("ASIGNACION", reserva=reserva, detalle=f"asignada a {elegido.id}")
        self._registrar("COBRO", reserva=reserva, monto=reserva.monto_total, detalle="prepago de la reserva")
        cliente = self.repo.clientes[reserva.cliente_id]
        self._avisar_cliente(cliente, mensajes.cliente_arriendo_exitoso(cliente, reserva, elegido), reserva)
        dueno = self.repo.propietarios.get(elegido.propietario_id)
        if dueno:
            self._avisar_propietario(dueno.id, mensajes.prop_reservado(
                dueno, elegido, reserva, tarifas.repartir(reserva.monto_total)[0]), reserva)
        self.repo.guardar()
        return elegido

    # Esta funcion hace que el operador, pueda mover una reserva confirmada a otro estacionamiento, verificando antes que no genere conflictos. Puede ser un estacionamiento de visita
    def reasignar_reserva(self, reserva_id, nuevo_estacionamiento_id, motivo="reasignación manual"):
        reserva = self._reserva(reserva_id)
        if reserva.estado != EstadoReserva.CONFIRMADA:
            raise ReglaNegocioError(f"Solo se reasignan reservas CONFIRMADAS, está {reserva.estado}.")
        if reserva.fin <= self.reloj.ahora():
            raise ReglaNegocioError("La reserva ya terminó.")
        nuevo = self._estacionamiento(nuevo_estacionamiento_id)
        if nuevo.id == reserva.estacionamiento_id:
            raise ReglaNegocioError("La reserva ya está asignada a ese estacionamiento.")
        incompatibilidad = self._motivo_incompatibilidad(nuevo, reserva.inicio, reserva.fin,
                                                         ignorar_id=reserva.id, permitir_visita=True)
        if incompatibilidad:
            raise ReglaNegocioError(f"No se puede reasignar a {nuevo.id}: {incompatibilidad}.")

        anterior = reserva.estacionamiento_id
        reserva.estacionamiento_id = nuevo.id
        reserva.propietario_id = nuevo.propietario_id
        reserva.motivo = motivo
        self._registrar("REASIGNACION", reserva=reserva, detalle=f"{anterior} -> {nuevo.id} ({motivo})")
        cliente = self.repo.clientes[reserva.cliente_id]
        self._avisar_cliente(cliente, mensajes.cliente_reasignada(cliente, reserva, anterior, nuevo.id, motivo), reserva)
        viejo = self.repo.estacionamientos.get(anterior)
        if viejo and viejo.propietario_id in self.repo.propietarios:
            self._avisar_propietario(viejo.propietario_id, mensajes.prop_reserva_movida(
                self.repo.propietarios[viejo.propietario_id], viejo, reserva), reserva)
        dueno = self.repo.propietarios.get(nuevo.propietario_id)
        if dueno:
            self._avisar_propietario(dueno.id, mensajes.prop_reservado(
                dueno, nuevo, reserva, tarifas.repartir(reserva.monto_total)[0]), reserva)
        self.repo.guardar()
        return nuevo

    #Esta funcion cierra una reserva con uno de tres resultados: finalizada (uso normal), sobretiempo, o no presentación. Luego liquida el reparto
    def registrar_resultado(self, reserva_id, resultado, bloques_exceso=0):
        reserva = self._reserva(reserva_id)
        if reserva.estado != EstadoReserva.CONFIRMADA:
            raise ReglaNegocioError(f"Solo se cierran reservas CONFIRMADAS (esta está {reserva.estado}).")
        ahora = self.reloj.ahora()

        if resultado == Resultado.NO_PRESENTADA:
            limite = reserva.inicio + timedelta(minutes=tarifas.ESPERA_NO_SHOW_MIN)
            if ahora < limite:
                raise ReglaNegocioError(
                    f"Aún no pasan {tarifas.ESPERA_NO_SHOW_MIN} minutos desde el inicio "
                    f"({limite:{FORMATO_HORA}}): el cliente todavía puede llegar.")
            penalizacion = int(reserva.monto_total * tarifas.PORCENTAJE_NO_SHOW)
            reembolso = reserva.monto_tarifa - penalizacion
            reserva.estado = EstadoReserva.NO_PRESENTADA
            reserva.monto_tarifa = 0
            reserva.monto_penalizacion = penalizacion
            reserva.motivo = "el cliente no se presentó"
            self._registrar("NO_SHOW", reserva=reserva, monto=penalizacion,
                            detalle="se cobra el 50% del valor reservado")
            if reembolso > 0:
                self._registrar("REEMBOLSO", reserva=reserva, monto=reembolso, detalle="reembolso del 50% restante")
        elif resultado in (Resultado.FINALIZADA, Resultado.SOBRETIEMPO):
            if ahora < reserva.fin:
                raise ReglaNegocioError(f"La reserva aún no termina (termina a las {reserva.fin:{FORMATO_HORA}}).")
            if resultado == Resultado.SOBRETIEMPO:
                if bloques_exceso < 1:
                    raise ReglaNegocioError("Debes indicar cuántos bloques de 30 min se excedió el cliente.")
                reserva.monto_penalizacion = bloques_exceso * tarifas.PENALIZACION_SOBRETIEMPO_BLOQUE
                self._registrar("SOBRETIEMPO", reserva=reserva, monto=reserva.monto_penalizacion,
                                detalle=f"{bloques_exceso} bloque(s) excedido(s) a {tarifas.clp(tarifas.PENALIZACION_SOBRETIEMPO_BLOQUE)} c/u")
            reserva.estado = EstadoReserva.FINALIZADA
            reserva.motivo = "reserva finalizada"
            self._registrar("FINALIZACION", reserva=reserva, monto=reserva.monto_tarifa,
                            detalle="uso completo de la reserva")
        else:
            raise ReglaNegocioError("Resultado no válido.")

        self._liquidar(reserva)
        cliente = self.repo.clientes[reserva.cliente_id]
        estado_texto = {Resultado.FINALIZADA: "finalizada", Resultado.SOBRETIEMPO: "con sobretiempo",
                        Resultado.NO_PRESENTADA: "no presentación"}[resultado]
        self._avisar_cliente(cliente, mensajes.cliente_cierre(cliente, reserva, estado_texto), reserva)
        self._avisar_admin(mensajes.admin_cierre(cliente, reserva, estado_texto), reserva)
        self.repo.guardar()
        return reserva

    #Funciones orientadas a la exposicion de informacion en la pantalla del sistema 

    #Se muestran los destindos posibles de estacionamientos
    def destinos_posibles(self, reserva):
        return [e for e in sorted(self.repo.estacionamientos.values(), key=lambda e: e.id)
                if e.id != reserva.estacionamiento_id
                and self._motivo_incompatibilidad(e, reserva.inicio, reserva.fin, ignorar_id=reserva.id,
                                                  permitir_visita=True) is None]

    #Muestra al propietario y a su estacionamiento correspondiente 
    def estacionamiento_de(self, propietario_id):
        for e in self.repo.estacionamientos.values():
            if e.tipo == TipoEstacionamiento.PRIVADO and e.propietario_id == propietario_id:
                return e
        return None

    #Reservas las reservas y a aque cliente corresponde 
    def reservas_de_cliente(self, cliente_id):
        return sorted((r for r in self.repo.reservas.values() if r.cliente_id == cliente_id),
                      key=lambda r: r.inicio)

    #Muestra a cada propietario y cuantas son sus reservas 
    def reservas_de_propietario(self, propietario_id):
        return sorted((r for r in self.repo.reservas.values() if r.propietario_id == propietario_id),
                      key=lambda r: r.inicio)

    #Funcion que filtra las reservas que tienen cierto estado
    def reservas_con_estado(self, *estados):
        return sorted((r for r in self.repo.reservas.values() if r.estado in estados),
                      key=lambda r: (r.inicio, r.id))

    #Muestra el ingrso total que consigue cada propietario
    def ingresos_de_propietario(self, propietario_id):
        return sum(l.a_propietario for l in self.repo.liquidaciones if l.propietario_id == propietario_id)

    #Muestra los bloques de tiempo en las horas del dia, los muestra para cada estacionamiento
    def mapa_dia(self, estacionamiento_id, dia, desde="07:00", hasta="20:00"):
        est = self._estacionamiento(estacionamiento_id)
        reservas = [r for r in self.repo.reservas.values()
                    if r.estacionamiento_id == est.id and r.estado == EstadoReserva.CONFIRMADA]
        inicio = ahora_con_hora(dia, desde)
        fin = ahora_con_hora(dia, hasta)
        filas = []
        for bloque in bloques_entre(inicio, fin):
            if any(r.inicio <= bloque < r.fin for r in reservas):
                simbolo = "R"
            else:
                estado = self._estado_bloque(est.id, bloque)
                simbolo = {"LIBERADO": "L", "BLOQUEADO": "B"}.get(estado, ".")
            filas.append((bloque, simbolo))
        return filas

    #Muestra el estado de cada estacionamiento 
    def tablero(self, momento):
        filas = []
        for est in sorted(self.repo.estacionamientos.values(), key=lambda e: (e.tipo, e.id)):
            reserva = next((r for r in self.repo.reservas.values()
                            if r.estado == EstadoReserva.CONFIRMADA and r.estacionamiento_id == est.id
                            and r.inicio <= momento < r.fin), None)
            if reserva:
                cliente = self.repo.clientes.get(reserva.cliente_id)
                estado = f"OCUPADO por externo (reserva #{reserva.id}, patente {cliente.patente if cliente else '?'})"
            elif est.tipo == TipoEstacionamiento.VISITA:
                estado = "LIBRE (respaldo de contingencias)"
            else:
                bloque = self._estado_bloque(est.id, momento.replace(minute=0 if momento.minute < 30 else 30))
                estado = {"LIBERADO": "LIBRE para reservar", "BLOQUEADO": "BLOQUEADO por su propietario"}.get(
                    bloque, "NO liberado (residente en casa)")
            filas.append((est, estado))
        return filas


def ahora_con_hora(dia, texto_hora):
    from datetime import datetime
    return datetime.strptime(f"{dia:{FORMATO_FECHA}} {texto_hora}", f"{FORMATO_FECHA} {FORMATO_HORA}")


#raise hace que el sistema laze un error a proposito, esto para rechazar una operacion 
#"class ReglaNegocioError(Exception)" es una forma de error inventado por el equipo para lanzar un error en caso que un regla este fallando
#Metodos con _ al inicio son ayudates internos que al final no son llamados desde afuera
#[e for e in lista if condicion] filtra una lista en una linea 
#sorted(..., key=lambda ...): ordena con un criterio propio. lambda es una mini función sin nombre.
#any(...) indica si al menos uno cumple una condicion
#ceil redondea hacia arriba
#.get() busca por clave sin fallar en caso que no exista 