/*
  app.js — comportamiento de la interfaz de SIGE.

  Cómo está organizado:
    1) Utilidades pequeñas ($, esc, pesos, avisos).
    2) Comunicación con el servidor: pedirEstado() trae todos los datos; accion() ejecuta algo.
    3) Una función render...() por pestaña: dibuja las tablas y listas con los datos recibidos.
    4) Los botones: cada uno llama a accion("nombre", {datos}). Las acciones están definidas
       en servidor_web.py (diccionario ACCIONES).
    5) refrescar() se ejecuta al cargar, después de cada acción y cada 2,5 segundos.
*/
"use strict";

// ---------------------------------------------------------------------------
// 1) Utilidades
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const HORAS = [];
for (let h = 6; h < 24; h++) for (const m of ["00", "30"]) HORAS.push(`${String(h).padStart(2, "0")}:${m}`);
const NOMBRE_DIAS = ["L", "M", "X", "J", "V", "S", "D"];
const CLASE_ESTADO = { PENDIENTE: "amarillo", CONFIRMADA: "azul", CANCELADA: "gris", LIBERADA: "celeste", FINALIZADA: "verde", NO_PRESENTADA: "rojo" };
const TABLAS = ["Reservas", "Historial", "Liquidaciones", "Notificaciones", "Estacionamientos", "Disponibilidad", "Propietarios", "Clientes"];

const pesos = (n) => "$" + Math.round(n).toLocaleString("es-CL");
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const insignia = (estado) => `<span class="estado e-${CLASE_ESTADO[estado] || "gris"}">${esc(estado)}</span>`;

let E = null;                 // último estado recibido del servidor
let firmas = {};              // para redibujar solo lo que cambió (así no se pierden las selecciones)
let notifVistas = null;       // última notificación que ya se mostró como aviso emergente
let notifLeidas = 0;          // última notificación vista en la pestaña Notificaciones
let pestana = "propietario";
let tablaActual = "Reservas";
let notifElegida = null;

// Aviso emergente. Al hacer clic se cierra (o ejecuta `alHacerClic` si se entrega una función).
function aviso(texto, tipo = "ok", titulo = "", alHacerClic = null) {
  const caja = document.createElement("div");
  caja.className = `toast ${tipo}`;
  caja.innerHTML = (titulo ? `<b>${esc(titulo)}</b>` : "") + esc(texto);
  caja.onclick = () => { caja.remove(); if (alHacerClic) alHacerClic(); };
  $("toasts").appendChild(caja);
  while ($("toasts").children.length > 4) $("toasts").firstChild.remove();
  setTimeout(() => caja.remove(), tipo === "error" ? 9000 : 5500);
}

function siCambio(clave, datos, dibujar) {
  const firma = JSON.stringify(datos);
  if (firmas[clave] === firma) return;
  firmas[clave] = firma;
  dibujar();
}

function llenarSelect(select, opciones, porDefecto = "") {
  const firma = JSON.stringify(opciones);
  if (select.dataset.firma === firma) return;
  const anterior = select.value;
  select.dataset.firma = firma;
  select.innerHTML = opciones.map((o) => `<option value="${esc(o.valor)}">${esc(o.texto)}</option>`).join("");
  const existe = (v) => opciones.some((o) => o.valor === v);
  select.value = existe(anterior) ? anterior : (existe(porDefecto) ? porDefecto : (opciones[0] ? opciones[0].valor : ""));
}

function sumarDias(fecha, dias) {
  const d = new Date(fecha + "T12:00:00");
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// 2) Comunicación con el servidor
// ---------------------------------------------------------------------------
async function pedirJSON(url) {
  const respuesta = await fetch(url);
  return respuesta.json();
}

async function accion(nombre, datos = {}) {
  try {
    const respuesta = await fetch("/api/accion", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accion: nombre, ...datos }),
    });
    const resultado = await respuesta.json();
    if (resultado.ok) {
      aviso(resultado.mensaje, "ok");
      if (resultado.advertencia) aviso(resultado.advertencia, "alerta", "Atención");
    } else {
      aviso(resultado.error, "error", "No se pudo realizar");
    }
    await refrescar();
    return resultado;
  } catch (e) {
    aviso("No se pudo comunicar con el servidor. ¿Sigue abierta la ventana de la terminal?", "error");
  }
}

async function refrescar() {
  try {
    E = await pedirJSON("/api/estado");
  } catch (e) {
    aviso("Se perdió la conexión con el servidor.", "error");
    return;
  }
  render();
  avisarNotificacionesNuevas();
  if (pestana === "propietario") await cargarMapa();
  if (pestana === "datos") await cargarTabla();
}

// ---------------------------------------------------------------------------
// 3) Dibujo de cada parte de la pantalla
// ---------------------------------------------------------------------------
function render() {
  renderReloj();
  renderExcel();
  renderPropietario();
  renderCliente();
  renderAdmin();
  renderNotificaciones();
}

function renderReloj() {
  $("reloj-texto").textContent = E.ahora;
  const modo = $("reloj-modo");
  modo.textContent = E.simulado ? "SIMULADA" : "HORA REAL";
  modo.className = "chip " + (E.simulado ? "alerta" : "ok");
  if (!$("reloj-fecha").value) $("reloj-fecha").value = E.dia;
  ajustarFechas();
}

// Si el reloj avanza, las fechas de los formularios no pueden quedar en el pasado.
function ajustarFechas() {
  const manana = sumarDias(E.dia, 1);
  for (const id of ["p-fecha", "c-fecha"]) {
    const campo = $(id);
    if (!campo.value || campo.value < E.dia) campo.value = manana;
  }
}

function renderExcel() {
  const x = E.excel;
  const chip = $("excel-estado");
  const mapa = { OK: ["ok", `Excel actualizado ${x.ultima}`], BLOQUEADO: ["alerta", "Excel abierto: pendiente de actualizar"],
                 SIN_OPENPYXL: ["error", "Falta instalar openpyxl"], ERROR: ["error", "Error al escribir el Excel"], PENDIENTE: ["alerta", "Excel sin generar"] };
  const [clase, texto] = mapa[x.estado] || ["alerta", x.estado];
  chip.className = "chip " + clase;
  chip.textContent = texto;
  $("d-ruta").textContent = x.ruta;
  const estado = $("d-estado");
  estado.className = "estado-excel " + clase;
  estado.textContent = x.mensaje || (x.estado === "OK" ? `Último guardado: ${x.ultima}. El archivo está al día.` : texto);
}

// ----- Propietario -----
function renderPropietario() {
  llenarSelect($("p-quien"), E.propietarios.map((p) => ({ valor: p.id, texto: `${p.id} — ${p.nombre} (${p.estacionamiento})` })));
  const p = E.propietarios.find((x) => x.id === $("p-quien").value);
  if (!p) return;
  siCambio("p-info", p, () => {
    $("p-info").innerHTML = `Estacionamiento <b>${esc(p.estacionamiento)}</b><br>RUT ${esc(p.rut)}<br>` +
      `Confiabilidad histórica: <b>${Math.round(p.confiabilidad * 100)}%</b><br>Ingresos acumulados: <b>${pesos(p.ingresos)}</b>`;
  });
  const propias = E.reservas.filter((r) => r.propietario_id === p.id && r.estacionamiento_id === p.estacionamiento);
  siCambio("p-reservas", [propias, E.ahora], () => {
    $("p-reservas").innerHTML = propias.length ? tablaHTML(
      ["N°", "Fecha", "Horario", "Estado", "Valor reserva", "Tu parte estimada (70%)"],
      propias.map((r) => [`#${r.id}`, r.fecha, `${r.inicio} a ${r.fin}`, insignia(r.estado), pesos(r.monto_total), pesos(r.monto_total * 0.7)]))
      : '<p class="vacio">Todavía no hay reservas en tu estacionamiento.</p>';
  });
}

async function cargarMapa() {
  const id = $("p-quien").value;
  const p = E && E.propietarios.find((x) => x.id === id);
  const fecha = $("p-fecha").value;
  if (!p || !fecha) return;
  const filas = await pedirJSON(`/api/mapa?estacionamiento=${encodeURIComponent(p.estacionamiento)}&fecha=${fecha}`);
  siCambio("p-mapa", [p.estacionamiento, fecha, filas], () => {
    $("p-mapa-titulo").textContent = `— ${p.estacionamiento}, ${fecha}`;
    const nombre = { L: "Liberado", R: "Reservado", B: "Bloqueado", ".": "No liberado" };
    $("p-mapa").innerHTML = filas.map((f) => `<div class="bloque b-${f.simbolo === "." ? "P" : f.simbolo}"><b>${f.hora}</b>${nombre[f.simbolo]}</div>`).join("");
  });
}

// ----- Cliente -----
function renderCliente() {
  llenarSelect($("c-quien"), E.clientes.map((c) => ({ valor: c.id, texto: `${c.id} — ${c.nombre} (${c.patente})` })));
  const c = E.clientes.find((x) => x.id === $("c-quien").value);
  if (!c) return;
  siCambio("c-info", c, () => {
    $("c-info").innerHTML = `RUT ${esc(c.rut)}<br>Patente autorizada: <b>${esc(c.patente)}</b>`;
  });
  const mias = E.reservas.filter((r) => r.cliente_id === c.id);
  siCambio("c-reservas", [mias, E.ahora], () => {
    if (!mias.length) { $("c-reservas").innerHTML = '<p class="vacio">Aún no tienes reservas.</p>'; return; }
    const opcionesBloques = [1, 2, 3, 4].map((n) => `<option value="${n}">+${n * 30} min</option>`).join("");
    $("c-reservas").innerHTML = tablaHTML(
      ["N°", "Fecha", "Horario", "Estacionamiento", "Estado", "Valor", "Acciones"],
      mias.map((r) => {
        let botones = "";
        if (r.estado === "PENDIENTE" || (r.estado === "CONFIRMADA" && !r.ya_comenzo)) {
          botones += `<button class="btn btn-rojo btn-fila" data-act="cancelar" data-id="${r.id}">Cancelar</button>`;
        }
        if (r.estado === "CONFIRMADA" && r.ya_comenzo && !r.ya_termino) {
          botones += `<button class="btn btn-rojo btn-fila" data-act="liberar_reserva" data-id="${r.id}">Terminar ahora</button>`;
        }
        if (r.estado === "CONFIRMADA" && !r.ya_termino) {
          botones += `<select class="ext-bloques">${opcionesBloques}</select><button class="btn btn-azul btn-fila" data-act="extender" data-id="${r.id}">Extender</button>`;
        }
        return [`#${r.id}`, r.fecha, `${r.inicio} a ${r.fin}`, r.estacionamiento_id || "sin asignar", insignia(r.estado), pesos(r.monto_total),
                `<div class="acciones">${botones || "—"}</div>`];
      }));
  });
}

// ----- Administrador -----
function renderAdmin() {
  const pendientes = E.reservas.filter((r) => r.estado === "PENDIENTE");
  siCambio("a-pendientes", [pendientes, E.ahora], () => {
    $("a-pendientes").innerHTML = pendientes.length ? tablaHTML(
      ["N°", "Cliente", "Fecha", "Horario", "Valor", "Asignar"],
      pendientes.map((r) => {
        const compat = r.compatibles || [];
        const opciones = compat.map((e) => `<option value="${e.id}">${e.id} (${Math.round(e.confiabilidad * 100)}%)</option>`).join("");
        const control = r.compatibles === undefined
          ? '<span class="vacio">La reserva ya comenzó</span>'
          : compat.length
            ? `<div class="acciones"><select class="asig-sel"><option value="">Automático (el más confiable)</option>${opciones}</select><button class="btn btn-azul btn-fila" data-act="asignar" data-id="${r.id}">Asignar</button></div>`
            : '<span class="vacio">Sin estacionamientos compatibles</span>';
        return [`#${r.id}`, `${esc(r.cliente)} (${esc(r.patente)})`, r.fecha, `${r.inicio} a ${r.fin}`, pesos(r.monto_total), control];
      })) : '<p class="vacio">No hay reservas pendientes.</p>';
  });

  const confirmadas = E.reservas.filter((r) => r.estado === "CONFIRMADA");
  siCambio("a-confirmadas", [confirmadas, E.ahora], () => {
    $("a-confirmadas").innerHTML = confirmadas.length ? tablaHTML(
      ["N°", "Cliente", "Fecha", "Horario", "Estac.", "Reasignar a", "Cerrar reserva"],
      confirmadas.map((r) => {
        const destinos = r.destinos === undefined ? null : r.destinos;
        const reasignar = destinos === null ? '<span class="vacio">Ya terminó</span>'
          : destinos.length ? `<div class="acciones"><select class="dest-sel">${destinos.map((d) => `<option value="${d}">${d}</option>`).join("")}</select><button class="btn btn-azul btn-fila" data-act="reasignar" data-id="${r.id}">Reasignar</button></div>`
          : '<span class="vacio">Sin destinos libres</span>';
        const cerrar = `<div class="acciones"><select class="res-sel"><option value="FINALIZADA">Finalizada</option><option value="SOBRETIEMPO">Sobretiempo</option><option value="NO_PRESENTADA">No se presentó</option></select>` +
          `<input type="number" class="exceso" min="1" max="16" value="1" title="Bloques de 30 min excedidos (solo sobretiempo)">` +
          `<button class="btn btn-verde btn-fila" data-act="cerrar" data-id="${r.id}">Cerrar</button></div>`;
        return [`#${r.id}`, `${esc(r.cliente)} (${esc(r.patente)})`, r.fecha, `${r.inicio} a ${r.fin}`, `<b>${esc(r.estacionamiento_id)}</b>`, reasignar, cerrar];
      })) : '<p class="vacio">No hay reservas confirmadas.</p>';
  });

  siCambio("a-tablero", E.tablero, () => {
    $("a-tablero").innerHTML = E.tablero.map((t) =>
      `<div class="puesto p-${t.codigo}"><b>${esc(t.id)}</b>${t.tipo === "VISITA" ? "Visita" : "Privado"}<small>${esc(t.estado)}</small></div>`).join("");
  });
}

// ----- Notificaciones -----
const ICONO = { CLIENTE: "Cliente", PROPIETARIO: "Propietario", ADMINISTRADOR: "Administración" };
const quien = (n) => (n.tipo === "ADMINISTRADOR" ? "Administración" : `${n.nombre} (${ICONO[n.tipo]})`);

function renderNotificaciones() {
  const todas = E.notificaciones;
  const sinLeer = todas.filter((n) => n.id > notifLeidas).length;
  const badge = $("badge-notif");
  badge.textContent = sinLeer;
  badge.classList.toggle("oculto", sinLeer === 0 || pestana === "notif");

  const personas = [{ valor: "", texto: "Todas" }];
  const vistos = new Set();
  for (const n of todas) {
    const clave = `${n.tipo}|${n.destinatario_id}`;
    if (!vistos.has(clave)) { vistos.add(clave); personas.push({ valor: clave, texto: quien(n) }); }
  }
  llenarSelect($("n-persona"), personas);
  const tipo = $("n-tipo").value, persona = $("n-persona").value;
  const lista = todas.filter((n) => (!tipo || n.tipo === tipo) && (!persona || `${n.tipo}|${n.destinatario_id}` === persona)).slice().reverse();
  siCambio("n-lista", [lista.map((n) => n.id), notifElegida, notifLeidas], () => {
    $("n-lista").innerHTML = lista.length ? lista.map((n) =>
      `<li data-notif="${n.id}" class="${n.id === notifElegida ? "activa" : ""}"><div class="quien"><span>Para: ${esc(quien(n))}</span><span>${esc(n.momento.slice(5))}</span></div><div class="asunto">${n.id > notifLeidas && pestana !== "notif" ? "● " : ""}${esc(n.asunto)}</div></li>`).join("")
      : '<li class="vacio">No hay notificaciones para este filtro.</li>';
  });
  const elegida = todas.find((n) => n.id === notifElegida);
  siCambio("n-detalle", elegida || null, () => {
    $("n-detalle").innerHTML = elegida
      ? `<span class="chip">Para: ${esc(quien(elegida))}</span> <span class="chip">${esc(elegida.momento)}</span><h3>${esc(elegida.asunto)}</h3><pre>${esc(elegida.mensaje)}</pre>`
      : '<p class="vacio">Selecciona una notificación para leerla completa.</p>';
  });
}

function avisarNotificacionesNuevas() {
  const maximo = E.notificaciones.reduce((m, n) => Math.max(m, n.id), 0);
  if (notifVistas === null) { notifVistas = maximo; notifLeidas = maximo; return; }   // al abrir, no se avisa lo antiguo
  const nuevas = E.notificaciones.filter((n) => n.id > notifVistas);
  notifVistas = maximo;
  if (pestana === "notif") notifLeidas = maximo;
  const abrir = (id) => () => { notifElegida = id; firmas["n-lista"] = firmas["n-detalle"] = null; cambiarPestana("notif"); };
  const mostrar = nuevas.slice(-2);
  for (const n of mostrar) aviso(n.asunto, "notif", `Notificación enviada a ${quien(n)}`, abrir(n.id));
  if (nuevas.length > mostrar.length) aviso(`${nuevas.length - mostrar.length} notificaciones más. Haz clic para verlas.`, "notif", "", abrir(nuevas[0].id));
}

// ----- Datos y Excel -----
async function cargarTabla() {
  const datos = await pedirJSON(`/api/tabla?nombre=${encodeURIComponent(tablaActual)}`);
  siCambio("d-tabla", [tablaActual, datos], () => {
    $("d-resumen").textContent = `Hoja "${datos.nombre}": ${datos.total} filas` + (datos.total > datos.filas.length ? ` (se muestran las últimas ${datos.filas.length}; el Excel tiene todas)` : "");
    $("d-tabla").innerHTML = datos.filas.length ? tablaHTML(datos.columnas, datos.filas.map((f) => f.map((v) => esc(v)))) : '<p class="vacio" style="padding:12px">Esta hoja todavía no tiene filas.</p>';
  });
}

function dibujarSubpestanas() {
  $("d-subtabs").innerHTML = TABLAS.map((t) => `<button data-tabla="${t}" class="${t === tablaActual ? "activa" : ""}">${t}</button>`).join("");
}

function tablaHTML(columnas, filas) {
  return `<table><thead><tr>${columnas.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
    filas.map((f) => `<tr>${f.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
}

// ---------------------------------------------------------------------------
// 4) Botones y eventos
// ---------------------------------------------------------------------------
function valoresPeriodo(prefijo) {
  return { fecha: $(`${prefijo}-fecha`).value, inicio: $(`${prefijo}-inicio`).value, fin: $(`${prefijo}-fin`).value };
}

function cambiarPestana(nombre) {
  pestana = nombre;
  document.querySelectorAll("#pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.tab === nombre));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("activo", p.id === `tab-${nombre}`));
  if (nombre === "notif" && E) { notifLeidas = E.notificaciones.reduce((m, n) => Math.max(m, n.id), 0); firmas["n-lista"] = null; }
  if (E) renderNotificaciones();
  refrescar();
}

function iniciarEventos() {
  document.querySelectorAll("#pestanas button").forEach((b) => (b.onclick = () => cambiarPestana(b.dataset.tab)));

  // Propietario
  $("p-liberar").onclick = () => accion("liberar", { propietario_id: $("p-quien").value, ...valoresPeriodo("p") });
  $("p-bloquear").onclick = () => accion("bloquear", { propietario_id: $("p-quien").value, ...valoresPeriodo("p"), motivo: $("p-motivo").value });
  $("p-recurrente").onclick = () => accion("recurrente", {
    propietario_id: $("p-quien").value, inicio: $("p-rec-inicio").value, fin: $("p-rec-fin").value,
    semanas: $("p-rec-semanas").value,
    dias: [...document.querySelectorAll("#p-dias input:checked")].map((i) => Number(i.value)),
  });
  for (const id of ["p-quien", "p-fecha"]) $(id).onchange = () => { firmas["p-info"] = firmas["p-reservas"] = null; render(); cargarMapa(); };

  // Cliente
  $("c-reservar").onclick = () => accion("reservar", { cliente_id: $("c-quien").value, ...valoresPeriodo("c") });
  $("c-quien").onchange = () => { firmas["c-info"] = firmas["c-reservas"] = null; render(); };
  $("c-nuevo-btn").onclick = () => $("c-nuevo").classList.toggle("oculto");
  $("c-n-registrar").onclick = async () => {
    const r = await accion("registrar_cliente", { nombre: $("c-n-nombre").value, rut: $("c-n-rut").value, patente: $("c-n-patente").value });
    if (r && r.ok) {
      ["c-n-nombre", "c-n-rut", "c-n-patente"].forEach((id) => ($(id).value = ""));
      $("c-nuevo").classList.add("oculto");
      const ultimo = E.clientes[E.clientes.length - 1];
      $("c-quien").value = ultimo.id; firmas["c-info"] = firmas["c-reservas"] = null; render();
    }
  };

  // Botones dentro de las tablas (se detectan por el atributo data-act)
  document.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-act]");
    if (boton) {
      const fila = boton.closest("tr");
      const id = boton.dataset.id, que = boton.dataset.act;
      if (que === "cancelar") accion("cancelar", { cliente_id: $("c-quien").value, reserva_id: id });
      if (que === "liberar_reserva") accion("liberar_reserva", { cliente_id: $("c-quien").value, reserva_id: id });
      if (que === "extender") accion("extender", { cliente_id: $("c-quien").value, reserva_id: id, bloques: fila.querySelector(".ext-bloques").value });
      if (que === "asignar") accion("asignar", { reserva_id: id, estacionamiento_id: fila.querySelector(".asig-sel").value });
      if (que === "reasignar") accion("reasignar", { reserva_id: id, destino: fila.querySelector(".dest-sel").value });
      if (que === "cerrar") accion("cerrar", { reserva_id: id, resultado: fila.querySelector(".res-sel").value, exceso: fila.querySelector(".exceso").value });
      return;
    }
    const item = evento.target.closest("[data-notif]");
    if (item) { notifElegida = Number(item.dataset.notif); firmas["n-lista"] = firmas["n-detalle"] = null; renderNotificaciones(); return; }
    const sub = evento.target.closest("[data-tabla]");
    if (sub) { tablaActual = sub.dataset.tabla; dibujarSubpestanas(); firmas["d-tabla"] = null; cargarTabla(); }
  });

  // Notificaciones
  $("n-tipo").onchange = $("n-persona").onchange = () => { firmas["n-lista"] = null; renderNotificaciones(); };

  // Reloj y datos
  $("btn-fijar").onclick = () => accion("reloj_fijar", { fecha: $("reloj-fecha").value, hora: $("reloj-hora").value });
  document.querySelectorAll("[data-avanzar]").forEach((b) => (b.onclick = () => accion("reloj_avanzar", { minutos: b.dataset.avanzar })));
  $("btn-hora-real").onclick = () => accion("reloj_real");
  $("btn-reiniciar").onclick = () => { if (confirm("Esto borra todas las reservas, el historial y las notificaciones. ¿Continuar?")) accion("reiniciar"); };
  $("btn-abrir-excel").onclick = $("d-abrir").onclick = () => accion("abrir_excel");
}

// ---------------------------------------------------------------------------
// 5) Inicio
// ---------------------------------------------------------------------------
function iniciar() {
  const opcionesHora = HORAS.map((h) => `<option value="${h}">${h}</option>`).join("");
  for (const id of ["reloj-hora", "p-inicio", "p-fin", "p-rec-inicio", "p-rec-fin", "c-inicio", "c-fin"]) $(id).innerHTML = opcionesHora;
  $("reloj-hora").value = "08:00";
  $("p-inicio").value = $("c-inicio").value = "10:00";
  $("p-fin").value = $("c-fin").value = "12:00";
  $("p-rec-inicio").value = "09:00";
  $("p-rec-fin").value = "13:00";
  $("p-rec-semanas").innerHTML = [1, 2, 3, 4].map((n) => `<option value="${n}">${n}</option>`).join("");
  $("p-rec-semanas").value = "2";
  $("p-dias").innerHTML = NOMBRE_DIAS.map((d, i) => `<label><input type="checkbox" value="${i}" ${i < 5 ? "checked" : ""}>${d}</label>`).join("");
  dibujarSubpestanas();
  iniciarEventos();
  refrescar();
  setInterval(refrescar, 2500);
}

iniciar();