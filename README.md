# SIGE — Sistema Inteligente de Gestión de Estacionamientos

SIGE es una aplicación web que permite que los propietarios de un edificio ofrezcan sus estacionamientos a terceros durante los horarios en que no los utilizan. Los clientes pueden solicitar reservas y un administrador se encarga de asignarlas. El propietario siempre conserva la prioridad sobre su propio espacio.

## 1. Integrantes

**INTEGRANTES:** Carlos Sanchez y Samuel Abdala · 
**ASIGNATURA:** Hito Integrativo Evaluativo · 
**FECHA:** 9 de noviembre de 2026

## 2. Requisitos

Para instalar y ejecutar SIGE se necesita:

- Python 3.8 o superior.
- Un navegador web actualizado, como Google Chrome, Microsoft Edge o Firefox.
- La librería `openpyxl`, utilizada para generar el archivo Excel.

## 3. Instalación y ejecución

1. Descargar y descomprimir el archivo del proyecto.
2. Abrir una terminal y ubicarse dentro de la carpeta del proyecto, donde se encuentra `app.py`.
3. Instalar las dependencias: "pip install -r requirements.txt"

4. Iniciar la aplicación: "python app.py"

Al iniciar, SIGE levanta el servidor y abre la aplicación en el navegador.
La dirección predeterminada es `http://127.0.0.1:8765`.
Si ese puerto está ocupado, el sistema busca otro puerto disponible.
Para cerrar la aplicación, volver a la terminal y presionar `Ctrl+C`.

## 4. Funcionalidades por tipo de usuario

SIGE contempla tres roles y seis funcionalidades principales: una obligatoria y una propia del grupo para cada rol, agrupando las operaciones relacionadas.

**Propietario**

*Funciones Obligatorias: Liberar y bloquear estacionamiento*
Funciones en el codigo: `liberar_estacionamiento`, `bloquear_estacionamiento` 
Permite ofrecer los bloques disponibles y bloquear el espacio cuando el propietario lo necesita.

*Funcion Propia: Definir horario recurrente*
Funcion en el codigo: `definir_horario_recurrente`
Permite liberar días y horarios de forma semanal, respetando los bloques que ya están bloqueados.

**Cliente**

*Funciones Obligatorias: Reservar y cancelar o liberar una reserva*  
Funciones en el codigo: `crear_reserva`, `cancelar_reserva`, `liberar_reserva`
Permite solicitar un estacionamiento, cancelar antes del inicio o terminar antes de la hora reservada.

*Funcion Propia: Extender una reserva*
Funcion en el codigo: `extender_reserva`
Permite agregar tiempo si existe disponibilidad y se cumplen las validaciones.

**Administrador**

*Funciones Obligatorias: Asignar y reasignar reservas*
Funciones en el codigo: `asignar_reserva`, `reasignar_reserva`
Permite confirmar solicitudes pendientes y cambiar el estacionamiento asignado cuando sea necesario.

*Funcion Propia: Registrar el resultado*  
Funcion en el codigo: `registrar_resultado`
Permite cerrar una reserva como finalizada, con sobretiempo o no presentada, aplicando los cobros correspondientes.

**Por qué elegimos las funcionalidades propias**

-*Definir horario recurrente*: Implementa el modelo híbrido de la Entrega 1 (rutina semanal más ajustes diarios), para que el propietario no libere su espacio día por día.

-*Extender una reserva**: Evita que el cliente caiga en sobretiempo ($2.700 por bloque), permitiéndole ampliar su uso solo si el espacio sigue libre y no choca con el propietario ni con otra reserva.

-*Registrar el resultado*: Aplica las penalizaciones que serian: no presentación y sobretiempo, ademas del reparto 70/20/10 de la Entrega 1, que genera los ingresos del propietario, administrador y del edificio.

## 5. Reglas de negocio implementadas

Las operaciones se validan antes de modificar los datos. Si una regla no se cumple, el sistema informa el motivo y evita dejar cambios parciales.

Las reglas con sus respectivos funcionamientos

*Prioridad del propietario*:  El propietario puede bloquear su estacionamiento. Si el bloqueo afecta reservas vigentes, el sistema intenta reubicarlas en un estacionamiento de visita; si no hay uno disponible, las cancela con reembolso del 100%. 

*Disponibilidad*: Solo se pueden reservar bloques que estén liberados y no estén bloqueados.

*No superposición*: Un estacionamiento no puede tener dos reservas que coincidan en horario. 

*Bloques y colchón*: Los horarios se organizan en bloques de 30 minutos y se considera un colchón de 30 minutos antes del regreso del propietario.

*Anticipación mínima*: Las reservas deben solicitarse con al menos 30 minutos de anticipación.

*Tarifa y tope*: Se cobran $900 por cada bloque de 30 minutos, con un máximo diario de $12.000.

*Cancelación*: Si se cancela con 60 minutos o más de anticipación, no se aplica penalización. Con menos anticipación, se retiene el valor del primer bloque ($900).

*No presentación*: Si el cliente no se presenta dentro de los 20 minutos posteriores al inicio, se registra la no presentación y se cobra el 50% del valor reservado.

*Sobretiempo*: Se cobran $2.700 por cada bloque de 30 minutos excedido.

*Reparto de ingresos*: los ingresos se reparten en 70/20/10, el 70% corresponde al propietario, el 20% al operador y el 10% a la administración del edificio. Las penalizaciones se entregan al 100% al propietario.

## 6. Clases y componentes principales

El código separa los datos, las reglas de negocio, el servidor y la interfaz. 
Entre las principales clases se encuentran:

*(`Propietario`, `Cliente`, `Estacionamiento`)*:  
**Archivo: modelos.py** 
Representan a los usuarios y los estacionamientos del sistema.

*`Reserva`*
**Archivo: `modelos.py`**
Representa un arriendo y mantiene sus montos, horarios y estado.

*`Evento`*
**Archivo: `modelos.py`**
Registra los cambios importantes para mantener un historial.

*`Liquidacion`*
**Archivo: `modelos.py`**
Es la clase encargada del reparto de los ingresos de una reserva.

*`Notificacion`*
**Archivo: `modelos.py`** 
Esta clase se encarga de los avisos dirigidos a los usuarios.

*`Reloj`*
**Archivo: `reloj.py`**
Proporciona la hora real o una hora simulada.

*`Repositorio`*
**Archivo: `repositorio.py`**
Guarda y recupera los datos del sistema.

*`ServicioSIGE`*
**Archivo: `servicio.py`**
Ejecuta las operaciones y aplica las reglas de negocio. |

*`AplicacionSIGE`*
**Archivo: `servidor_web.py`**
Conecta el repositorio, el reloj y el servicio con el servidor web. |


Una reserva puede pasar por distintos estados durante su ciclo: 
`PENDIENTE`, `CONFIRMADA`, `FINALIZADA`, `LIBERADA`, `CANCELADA` o `NO_PRESENTADA`.

## 7. Organización de archivos y arquitectura

El proyecto utiliza cuatro capas principales:

Interfaz → Servidor → Servicio (reglas de negocio) → Repositorio (datos)

Esta separación permite modificar la interfaz sin tener que cambiar directamente las reglas de negocio o la forma en que se guardan los datos.

Los nombres de las carpetas con su respectiva funcion:

*`app.py`*
Este es el archivo que hace arrancar todo lo demas, aqui se ejecuta todo

*`servidor_web.py`*
Recibe las acciones de la interfaz, llama al servicio y entrega las respuestas.

*carpeta `web`* 
Contiene la interfaz: `index.html`, `app.js` y `estilos.css`.

*`servicio.py`* 
Contiene las operaciones principales y las validaciones de las reglas de negocio.

*`modelos.py`*
Define las clases y estructuras de datos del sistema

*`repositorio.py`*
Guarda y recupera la información mediante archivos CSV y coordina la actualización del Excel.

*`tarifas.py`, `reloj.py`, `mensajes.py`*
Constantes y cálculos de cobros; hora real o simulada; textos de las notificaciones. 


*`exportador_excel.py`*
Construye el archivo Excel con las tablas y el resumen.

*`datos_demo.py'*
Crea los datos de ejemplo del edificio para demostración.

## 8. Almacenamiento de datos y archivo Excel

La información se guarda en la carpeta `datos/` después de cada operación.
Cuando se vuelve a iniciar la aplicación, SIGE recupera los datos guardados para continuar trabajando.

El sistema conserva archivos CSV para las distintas tablas, entre ellas:

- `reservas.csv`: estado y datos de las reservas (cliente, estacionamiento, inicio, fin, estado y tres montos: valor total, tarifa cobrada y penalización).

- `historial.csv`: registro de los eventos y cambios realizados (momento, tipo de evento, reserva, estacionamiento, cliente, fecha, horas, estado, monto y detalle).

- `liquidaciones.csv`: distribución de los ingresos (parte del propietario, del operador y de la administración).

- `disponibilidad.csv`: bloques liberados o bloqueados (estacionamiento, bloque de 30 minutos y estado).

- `notificaciones.csv`: avisos generados (destinatario, asunto, mensaje y reserva).

- Archivos de propietarios, clientes y estacionamientos: datos principales de cada elemento.

El historial registra 14 tipos de evento (creación, asignación, cobro, cancelación, reembolso, extensión, reasignación, bloqueo, sobretiempo, no presentación, entre otros). 
Es la base del dashboard de la siguiente entrega.

Además, genera `SIGE_datos.xlsx`, que contiene las hojas:
*Resumen, Reservas, Historial, Liquidaciones, Notificaciones, Disponibilidad, Estacionamientos, Propietarios y Clientes*.

El Excel se actualiza después de cada operación.

Para consultarlo mientras SIGE está funcionando, se debe utilizar el botón **Abrir Excel**. 

Este botón abre una copia actualizada para evitar que el archivo original quede bloqueado por Excel.

Si al ejecutar no aparecen horarios disponibles, usar el botón Reiniciar datos.

## 9. Notificaciones

SIGE genera avisos cuando ocurre una operación que afecta a alguno de los usuarios. 
Las notificaciones aparecen en la interfaz —como avisos emergentes y en la pestaña **Notificaciones**— y también quedan registradas en `notificaciones.csv` y en la hoja Notificaciones del Excel.

Algunos ejemplos:

- Cuando el administrador asigna la reserva, el cliente recibe el aviso *“¡Arriendo exitoso!”*, con el estacionamiento, fecha, horario, patente, valor e instrucciones de ingreso.

- Cuando el propietario bloquea un horario que afecta una reserva, el cliente recibe el aviso de reubicación o cancelación y el administrador el de contingencia.

*Privacidad*: al propietario no se le informa el nombre ni la patente del cliente. Esa información queda disponible para el administrador.

*Importante*: las notificaciones son simuladas y utilizan el canal de la aplicación, NO se envían realmente por correo electrónico, SMS ni WhatsApp, esto debido a que este es solo un prototipo, proximamente se podria lograr una notificacion por correo.

## 10. Decisiones técnicas

-*Validar antes de modificar.*
Todas las operaciones siguen el orden validar, modificar, registrar, avisar y guardar, así un intento inválido nunca deja datos a medias.

-*Bloques de 30 minutos.*
Igual que el dataset de la Entrega 1; cada bloque liberado es una fila, lo que simplifica comprobar conflictos.

-*CSV en vez de base de datos.* 
Los CSV se abren en Excel y sirven para el dashboard; a cambio, se reescriben completos en cada operación, para este volumen de datos es algo realmente aceptable.

-*Reserva en dos pasos.*
Queda pendiente hasta que el administrador la asigna, y recién ahí se cobra, para no cobrar algo que quizá no se pueda ofrecer.

## 11. Limitaciones y próximos pasos

Las siguientes funciones todavía no están implementadas o tienen un alcance limitado en esta versión:

-*Inicio de sesión y pagos*: No hay autenticación (se elige el usuario de una lista) ni pasarela de pago; los cobros solo se registran.

-*Oferta automática*: Los filtros de franja horaria, confiabilidad mínima del 80% y ventana mínima de 2 horas definidos en la Entrega 1 no se aplican automáticamente. Aquí el propietario libera sus horarios libremente y la confiabilidad solo ordena la asignación.
