/* Usuarios (solo Administrador): alta, edicion y eliminacion */
async function cargarUsuarios() {
    const roles = await api('/api/admin/roles');
    llenarSelect('usr-rol', roles, 'id_rol', r => r.nombre_rol, null);
    estado.usuarios = await api('/api/admin/usuarios');
    filasTabla('tabla-usuarios', estado.usuarios.map(u => `
        <tr><td>${u.id_usuario}</td><td>${esc(u.nombre)}</td><td>${esc(u.email)}</td><td>${esc(u.nombre_rol) || 'Sin rol'}</td>
        <td><button class="btn btn-mini" onclick="editarUsuario(${u.id_usuario})">Editar</button>${u.id_usuario === estado.usuario.id_usuario ? '' : `<button class="btn btn-mini btn-danger" onclick="eliminarUsuario(${u.id_usuario})">Eliminar</button>`}</td></tr>`).join(''), 5, 'Sin usuarios');
}

function limpiarUsuario() {
    $('form-usuario').reset();
    $('usr-id').value = '';
    $('usr-pass').required = true;
    $('usr-pass').placeholder = 'Minimo 6 caracteres';
    modoEdicion('usr', 'Nuevo usuario', false);
}

function editarUsuario(id) {
    const u = estado.usuarios.find(x => x.id_usuario === id);
    $('usr-id').value = u.id_usuario;
    $('usr-nombre').value = u.nombre;
    $('usr-email').value = u.email;
    $('usr-rol').value = u.id_rol;
    $('usr-pass').value = '';
    $('usr-pass').required = false;
    $('usr-pass').placeholder = 'Dejar vacio para no cambiarla';
    modoEdicion('usr', 'Editar usuario', true);
}

async function eliminarUsuario(id) {
    const u = estado.usuarios.find(x => x.id_usuario === id);
    if (!confirm(`Eliminar al usuario "${u.nombre}"? Esta accion no se puede deshacer.`)) return;
    if (await ejecutar(() => api(`/api/admin/usuarios/${id}`, 'DELETE')) && $('usr-id').value == id) limpiarUsuario();
}

$('form-usuario').addEventListener('submit', async ev => {
    ev.preventDefault();
    const id = $('usr-id').value;
    const cuerpo = {
        nombre: $('usr-nombre').value,
        email: $('usr-email').value,
        password: $('usr-pass').value,
        id_rol: parseInt($('usr-rol').value)
    };
    if (await ejecutar(() => id ? api(`/api/admin/usuarios/${id}`, 'PUT', cuerpo) : api('/api/admin/usuarios', 'POST', cuerpo))) limpiarUsuario();
});
$('usr-cancelar').addEventListener('click', limpiarUsuario);
