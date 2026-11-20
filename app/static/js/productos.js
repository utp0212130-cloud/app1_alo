/* Productos: tabla, alta, edicion y borrado */
async function cargarProductos() {
    estado.productos = await api('/api/productos/lista');

    const alm = veAlmacen();

    filasTabla(
        'tabla-productos',
        estado.productos.map(p => `
            <tr class="${p.stock_actual <= p.stock_minimo ? 'stock-bajo' : ''}">
                <td>${p.id_producto}</td>
                <td>${esc(p.codigo_barras) || 'N/A'}</td>
                <td>${esc(p.nombre)}</td>
                <td>${esc(p.categoria) || 'Sin categoria'}</td>

                ${alm
                    ? `<td>${esc(p.proveedor) || 'Sin proveedor'}</td>
                       <td>${dinero(p.precio_compra)}</td>`
                    : ''
                }

                <td>${dinero(p.precio_venta)}</td>

                <td>${p.stock_actual}</td>

                ${alm
                    ? `<td>
                        <button
                            class="btn btn-mini"
                            onclick="editarProducto(${p.id_producto})">
                            Editar
                        </button>

                        <button
                            class="btn btn-mini btn-danger"
                            onclick="borrarProducto(${p.id_producto})">
                            Eliminar
                        </button>
                       </td>`
                    : ''
                }
            </tr>
        `).join(''),
        9,
        'No hay productos registrados'
    );

    const textoProd = p =>
        `${p.nombre} (stock: ${p.stock_actual} | ${dinero(p.precio_venta)})`;

    if (veVentas()) {
        llenarSelect(
            'venta-producto',
            estado.productos,
            'id_producto',
            textoProd,
            'Seleccione el producto'
        );
    }

    if (alm) {
        llenarSelect(
            'entrada-producto',
            estado.productos,
            'id_producto',
            textoProd,
            'Seleccione el producto'
        );
    }
}


function limpiarProducto() {
    $('form-producto').reset();

    $('prod-id').value = '';

    // Valor inicial del stock
    $('prod-stock').value = 0;

    modoEdicion('prod', 'Nuevo producto', false);
}


function editarProducto(id) {
    const p = estado.productos.find(
        x => x.id_producto === id
    );

    if (!p) return;

    $('prod-id').value = p.id_producto;

    $('prod-codigo').value =
        p.codigo_barras || '';

    $('prod-nombre').value =
        p.nombre;

    $('prod-desc').value =
        p.descripcion || '';

    $('prod-cat').value =
        p.id_categoria || '';

    $('prod-prov').value =
        p.id_proveedor || '';

    $('prod-pc').value =
        p.precio_compra;

    $('prod-pv').value =
        p.precio_venta;

    // AQUÍ SE CARGA EL STOCK ACTUAL
    $('prod-stock').value =
        p.stock_actual;

    $('prod-min').value =
        p.stock_minimo;

    modoEdicion(
        'prod',
        'Editar producto',
        true
    );
}


async function borrarProducto(id) {
    if (
        !confirm(
            'Eliminar este producto del catalogo? Su historial de ventas se conserva.'
        )
    ) return;

    if (
        await ejecutar(
            () =>
                api(
                    `/api/almacen/productos/${id}`,
                    'DELETE'
                )
        )
        &&
        $('prod-id').value == id
    ) {
        limpiarProducto();
    }
}


$('form-producto').addEventListener(
    'submit',
    async ev => {

        ev.preventDefault();

        const id =
            $('prod-id').value;

        const cuerpo = {

            codigo_barras:
                $('prod-codigo').value,

            nombre:
                $('prod-nombre').value,

            descripcion:
                $('prod-desc').value,

            id_categoria:
                $('prod-cat').value
                    ? parseInt(
                        $('prod-cat').value
                    )
                    : null,

            id_proveedor:
                $('prod-prov').value
                    ? parseInt(
                        $('prod-prov').value
                    )
                    : null,

            precio_compra:
                parseFloat(
                    $('prod-pc').value
                ) || 0,

            precio_venta:
                parseFloat(
                    $('prod-pv').value
                ) || 0,

            // AQUÍ SE ENVÍA EL STOCK
            stock_actual:
                parseInt(
                    $('prod-stock').value
                ) || 0,

            stock_minimo:
                parseInt(
                    $('prod-min').value
                ) || 0
        };


        if (
            await ejecutar(
                () =>
                    id
                        ? api(
                            `/api/almacen/productos/${id}`,
                            'PUT',
                            cuerpo
                        )
                        : api(
                            '/api/almacen/productos',
                            'POST',
                            cuerpo
                        )
            )
        ) {
            limpiarProducto();
        }
    }
);


$('prod-cancelar').addEventListener(
    'click',
    limpiarProducto
);


$('form-entrada').addEventListener(
    'submit',
    async ev => {

        ev.preventDefault();

        const ok =
            await ejecutar(
                () =>
                    api(
                        '/api/almacen/entradas',
                        'POST',
                        {
                            id_producto:
                                parseInt(
                                    $('entrada-producto').value
                                ),

                            cantidad:
                                parseInt(
                                    $('entrada-cantidad').value
                                ) || 0,

                            motivo:
                                $('entrada-motivo').value
                        }
                    )
            );

        if (ok) {

            $('entrada-cantidad').value =
                1;

            $('entrada-motivo').value =
                '';
        }
    }
);