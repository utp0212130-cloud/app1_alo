/* Sesion, navegacion y carga general de datos */
async function cargarTodo() {
    if (!estado.usuario) return;
    try {
        if (veAlmacen()) { await cargarCatalogos(); await cargarMovimientos(); }
        await cargarProductos();
        if (veVentas()) await cargarVentas();
        if (esAdmin()) await cargarUsuarios();
    } catch (e) {
        if (e.message !== 'SESION') aviso('Error al cargar datos: ' + e.message, 'error');
    }
}

function cerrarSesion() {
    estado.token = null;
    estado.usuario = null;
    $('app').hidden = true;
    $('pantalla-login').hidden = false;
    $('password').value = '';
    $('login-error').hidden = true;
    limpiarProducto(); limpiarCategoria(); limpiarProveedor(); limpiarUsuario();
    $('form-salida').reset(); $('form-entrada').reset(); $('venta-motivo-caja').hidden = true;
    $('total-ventas').textContent = '$0.00'; $('unidades-ventas').textContent = '';
}

$('form-login').addEventListener('submit', async ev => {
    ev.preventDefault();
    const error = $('login-error');
    const boton = $('btn-login');
    error.hidden = true;
    boton.disabled = true;
    boton.textContent = 'Ingresando...';
    try {
        const data = await api('/api/login', 'POST', { email: $('email').value, password: $('password').value });
        estado.token = data.token;
        estado.usuario = data;
        $('usuario-nombre').textContent = data.nombre;
        $('usuario-rol').textContent = data.nombre_rol;
        $('pantalla-login').hidden = true;
        $('app').hidden = false;
        aplicarRoles();
        mostrarVista('productos');
        $('password').value = '';
        await cargarTodo();
    } catch (e) {
        error.textContent = e.message === 'Failed to fetch' ? 'No se pudo conectar con el servidor' : e.message;
        error.hidden = false;
    } finally {
        boton.disabled = false;
        boton.textContent = 'Iniciar sesion';
    }
});

$('menu').addEventListener('click', ev => {
    const boton = ev.target.closest('.nav-item');
    if (boton) mostrarVista(boton.dataset.vista);
});
$('btn-salir').addEventListener('click', cerrarSesion);
