/* Categorias, proveedores e historial de movimientos */
async function cargarCatalogos() {
    estado.categorias = await api('/api/categorias/lista');
    estado.proveedores = await api('/api/proveedores/lista');

    filasTabla('tabla-categorias', estado.categorias.map(c => `
        <tr><td>${c.id_categoria}</td><td>${esc(c.nombre)}</td><td>${esc(c.descripcion)}</td>
        <td><button class="btn btn-mini" onclick="editarCategoria(${c.id_categoria})">Editar</button><button class="btn btn-mini btn-danger" onclick="borrarCategoria(${c.id_categoria})">Eliminar</button></td></tr>`).join(''), 4, 'Sin categorias');

    filasTabla('tabla-proveedores', estado.proveedores.map(p => `
        <tr><td>${p.id_proveedor}</td><td>${esc(p.nombre_empresa)}</td><td>${esc(p.contacto_nombre)}</td><td>${esc(p.telefono)}</td><td>${esc(p.email)}</td>
        <td><button class="btn btn-mini" onclick="editarProveedor(${p.id_proveedor})">Editar</button><button class="btn btn-mini btn-danger" onclick="borrarProveedor(${p.id_proveedor})">Eliminar</button></td></tr>`).join(''), 6, 'Sin proveedores');

    llenarSelect('prod-cat', estado.categorias, 'id_categoria', c => c.nombre, 'Sin categoria');
    llenarSelect('prod-prov', estado.proveedores, 'id_proveedor', p => p.nombre_empresa, 'Sin proveedor');
}

async function cargarMovimientos() {
    const filas = await api('/api/almacen/historial');
    filasTabla('tabla-movimientos', filas.map(h => `
        <tr><td>${esc(fecha(h.fecha_movimiento))}</td><td>${esc(h.producto)}</td><td>${esc(h.tipo_movimiento)}</td>
        <td>${h.cantidad}</td><td>${esc(h.motivo)}</td><td>${esc(h.usuario) || '-'}</td></tr>`).join(''), 6, 'Sin movimientos todavia');
}

// ---------- Categorias ----------
function limpiarCategoria() { $('form-categoria').reset(); $('cat-id').value = ''; modoEdicion('cat', 'Nueva categoria', false); }

function editarCategoria(id) {
    const c = estado.categorias.find(x => x.id_categoria === id);
    $('cat-id').value = c.id_categoria; $('cat-nombre').value = c.nombre; $('cat-desc').value = c.descripcion || '';
    modoEdicion('cat', 'Editar categoria', true);
}

async function borrarCategoria(id) {
    if (!confirm('Eliminar categoria? Sus productos quedaran sin categoria.')) return;
    if (await ejecutar(() => api(`/api/almacen/categorias/${id}`, 'DELETE')) && $('cat-id').value == id) limpiarCategoria();
}

$('form-categoria').addEventListener('submit', async ev => {
    ev.preventDefault();
    const id = $('cat-id').value;
    const cuerpo = { nombre: $('cat-nombre').value, descripcion: $('cat-desc').value };
    if (await ejecutar(() => id ? api(`/api/almacen/categorias/${id}`, 'PUT', cuerpo) : api('/api/almacen/categorias', 'POST', cuerpo))) limpiarCategoria();
});
$('cat-cancelar').addEventListener('click', limpiarCategoria);

// ---------- Proveedores ----------
function limpiarProveedor() { $('form-proveedor').reset(); $('prv-id').value = ''; modoEdicion('prv', 'Nuevo proveedor', false); }

function editarProveedor(id) {
    const p = estado.proveedores.find(x => x.id_proveedor === id);
    $('prv-id').value = p.id_proveedor; $('prv-nombre').value = p.nombre_empresa; $('prv-contacto').value = p.contacto_nombre || '';
    $('prv-tel').value = p.telefono || ''; $('prv-email').value = p.email || ''; $('prv-dir').value = p.direccion || '';
    modoEdicion('prv', 'Editar proveedor', true);
}

async function borrarProveedor(id) {
    if (!confirm('Eliminar proveedor? Sus productos quedaran sin proveedor.')) return;
    if (await ejecutar(() => api(`/api/almacen/proveedores/${id}`, 'DELETE')) && $('prv-id').value == id) limpiarProveedor();
}

$('form-proveedor').addEventListener('submit', async ev => {
    ev.preventDefault();
    const id = $('prv-id').value;
    const cuerpo = { nombre_empresa: $('prv-nombre').value, contacto_nombre: $('prv-contacto').value,
                     telefono: $('prv-tel').value, email: $('prv-email').value, direccion: $('prv-dir').value };
    if (await ejecutar(() => id ? api(`/api/almacen/proveedores/${id}`, 'PUT', cuerpo) : api('/api/almacen/proveedores', 'POST', cuerpo))) limpiarProveedor();
});
$('prv-cancelar').addEventListener('click', limpiarProveedor);
