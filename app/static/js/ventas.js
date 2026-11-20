/* Ventas: salidas de inventario, total vendido y ultimas salidas */
async function cargarVentas() {
    const total = await api('/api/ventas/total');
    $('total-ventas').textContent = dinero(total.total_vendido);
    $('unidades-ventas').textContent = `${total.unidades_vendidas} unidad(es) vendida(s) en total`;

    const filas = await api('/api/ventas/historial');
    filasTabla('tabla-salidas', filas.map(h => `
        <tr><td>${esc(fecha(h.fecha_movimiento))}</td><td>${esc(h.producto)}</td><td>${h.tipo === 'VENTA' ? 'Venta' : 'Retiro'}</td>
        <td>${h.cantidad}</td><td>${h.tipo === 'VENTA' ? dinero(h.total) : '-'}</td><td>${esc(h.usuario) || '-'}</td></tr>`).join(''), 6, 'Sin movimientos todavia');
}

$('venta-tipo').addEventListener('change', () => { $('venta-motivo-caja').hidden = $('venta-tipo').value !== 'RETIRO'; });

$('form-salida').addEventListener('submit', async ev => {
    ev.preventDefault();
    const ok = await ejecutar(() => api('/api/ventas/registrar', 'POST', {
        id_producto: parseInt($('venta-producto').value),
        cantidad: parseInt($('venta-cantidad').value) || 0,
        tipo: $('venta-tipo').value,
        motivo: $('venta-motivo').value
    }));
    if (ok) { $('venta-cantidad').value = 1; $('venta-motivo').value = ''; }
});

$('btn-total').addEventListener('click', async () => {
    try { await cargarVentas(); aviso('Total actualizado'); }
    catch (e) { if (e.message !== 'SESION') aviso(e.message, 'error'); }
});
