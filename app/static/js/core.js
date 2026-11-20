/* Nucleo: estado, utilidades, llamadas a la API y avisos */
const estado = { token: null, usuario: null, productos: [], categorias: [], proveedores: [], usuarios: [] };

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const dinero = n => '$' + (parseFloat(n) || 0).toFixed(2);
const fecha = f => new Date(f).toLocaleString();
const rolActual = () => (estado.usuario ? estado.usuario.nombre_rol : null);
const esAdmin = () => rolActual() === 'Administrador';
const veAlmacen = () => ['Administrador', 'Almacenista'].includes(rolActual());
const veVentas = () => ['Administrador', 'Vendedor'].includes(rolActual());

function aviso(texto, tipo = 'ok') {
    const el = document.createElement('div');
    el.className = 'aviso ' + (tipo === 'error' ? 'error' : '');
    el.textContent = texto;
    $('avisos').appendChild(el);
    setTimeout(() => el.remove(), 4500);
}

function textoError(data) {
    if (!data || !data.detail) return 'Error desconocido';
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map(d => d.msg).join(', ');
    return JSON.stringify(data.detail);
}

async function api(ruta, metodo = 'GET', cuerpo = null) {
    const headers = {};
    if (estado.token) headers['Authorization'] = 'Bearer ' + estado.token;
    if (cuerpo) headers['Content-Type'] = 'application/json';
    const res = await fetch(ruta, { method: metodo, headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
    let data = null;
    try { data = await res.json(); } catch (e) { /* sin cuerpo */ }
    if (res.status === 401 && estado.token) {
        cerrarSesion();
        aviso(textoError(data), 'error');
        throw new Error('SESION');
    }
    if (!res.ok) throw new Error(textoError(data));
    return data;
}

// Ejecuta una accion, muestra el resultado y recarga los datos. Devuelve true si salio bien.
async function ejecutar(accion) {
    try {
        const data = await accion();
        if (data && data.mensaje) aviso(data.mensaje);
        await cargarTodo();
        return true;
    } catch (e) {
        if (e.message !== 'SESION') aviso(e.message, 'error');
        return false;
    }
}

function llenarSelect(id, items, valor, texto, vacio) {
    const sel = $(id);
    const previo = sel.value;
    sel.innerHTML = (vacio ? `<option value="">${esc(vacio)}</option>` : '') +
        items.map(i => `<option value="${i[valor]}">${esc(texto(i))}</option>`).join('');
    sel.value = previo;
}

function filasTabla(idTabla, html, columnas, mensajeVacio) {
    $(idTabla).querySelector('tbody').innerHTML = html || `<tr><td class="vacio" colspan="${columnas}">${mensajeVacio}</td></tr>`;
}

// Muestra u oculta elementos segun el rol (atributo data-roles="Rol1,Rol2" o "*")
function aplicarRoles() {
    document.querySelectorAll('[data-roles]').forEach(el => {
        const permitidos = el.dataset.roles.split(',');
        el.hidden = !(permitidos.includes('*') || permitidos.includes(rolActual()));
    });
}

function mostrarVista(nombre) {
    document.querySelectorAll('.vista').forEach(v => v.hidden = v.id !== 'vista-' + nombre);
    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('activo', b.dataset.vista === nombre));
}

// Prepara un formulario "crear / editar" con id oculto
function modoEdicion(prefijo, titulo, editando) {
    $(prefijo + '-titulo').textContent = titulo;
    $(prefijo + '-cancelar').hidden = !editando;
    if (editando) $(prefijo + '-titulo').scrollIntoView({ behavior: 'smooth', block: 'center' });
}
