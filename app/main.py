import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Optional

import psycopg2
import psycopg2.errors
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from security import crear_token, esta_hasheada, hash_password, leer_token, verificar_password

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
load_dotenv(BASE_DIR / ".env")

# Si no defines SECRET_KEY en .env, se genera una al arrancar (las sesiones se pierden al reiniciar)
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

ADMIN = "Administrador"
ALMACENISTA = "Almacenista"
VENDEDOR = "Vendedor"

app = FastAPI(title="API de Roles e Inventario")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ----------------------------------------------------------------------------
# Base de datos
# ----------------------------------------------------------------------------
@contextmanager
def get_cursor():
    """Abre conexion, hace commit al terminar y rollback si algo falla."""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    except psycopg2.OperationalError:
        raise HTTPException(status_code=503, detail="No se pudo conectar a la base de datos")
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un registro con ese correo o codigo de barras")
    except psycopg2.Error as e:
        conn.rollback()
        # Solo la primera linea (sin el CONTEXT de PL/pgSQL)
        mensaje = (e.pgerror or str(e)).splitlines()[0].replace("ERROR:", "").strip()
        raise HTTPException(status_code=400, detail=mensaje)
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Autenticacion y permisos por rol
# ----------------------------------------------------------------------------
def usuario_actual(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Debes iniciar sesion")
    datos = leer_token(authorization[7:], SECRET_KEY)
    if not datos:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada")
    # Se consulta la BD para usar el rol ACTUAL (si el usuario se edito o se borro, se nota de inmediato)
    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id_usuario, u.nombre, r.nombre_rol
               FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol WHERE u.id_usuario = %s""",
            (datos["id_usuario"],),
        )
        u = cur.fetchone()
    if not u:
        raise HTTPException(status_code=401, detail="Tu usuario ya no existe")
    return {"id_usuario": u["id_usuario"], "nombre": u["nombre"], "rol": u["nombre_rol"]}


def requiere_roles(*roles_permitidos):
    def validar(usuario=Depends(usuario_actual)):
        if usuario["rol"] not in roles_permitidos:
            raise HTTPException(status_code=403, detail="Tu rol no tiene permiso para esta accion")
        return usuario

    return validar


solo_admin = requiere_roles(ADMIN)
almacen = requiere_roles(ADMIN, ALMACENISTA)
ventas = requiere_roles(ADMIN, VENDEDOR)


# ----------------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------------
class LoginData(BaseModel):
    email: str
    password: str


class NuevoUsuario(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    id_rol: int


class ActualizarUsuario(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    id_rol: int
    password: Optional[str] = None  # si viene vacio, no se cambia


class NuevoProducto(BaseModel):
    codigo_barras: Optional[str] = ""
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: Optional[str] = ""
    id_categoria: Optional[int] = None
    id_proveedor: Optional[int] = None
    precio_compra: float = Field(default=0.00, ge=0)
    precio_venta: float = Field(default=0.00, ge=0)
    stock_actual: int = Field(default=0, ge=0)
    stock_minimo: int = Field(default=5, ge=0)


class Entrada(BaseModel):
    id_producto: int
    cantidad: int = Field(gt=0)
    motivo: Optional[str] = ""


class Salida(BaseModel):
    id_producto: int
    cantidad: int = Field(gt=0)
    tipo: Literal["VENTA", "RETIRO"] = "VENTA"
    motivo: Optional[str] = ""


# ----------------------------------------------------------------------------
# Pagina principal y login
# ----------------------------------------------------------------------------
@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/login")
def login(data: LoginData):
    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id_usuario, u.nombre, u.password_hash, r.nombre_rol
               FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol
               WHERE LOWER(u.email) = LOWER(%s)""",
            (data.email.strip(),),
        )
        u = cur.fetchone()
        if not u or not verificar_password(data.password, u["password_hash"]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        # Si la contrasena seguia en texto plano, se guarda ya hasheada
        if not esta_hasheada(u["password_hash"]):
            cur.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id_usuario = %s",
                (hash_password(data.password), u["id_usuario"]),
            )

    token = crear_token(
        {"id_usuario": u["id_usuario"], "nombre": u["nombre"], "rol": u["nombre_rol"]}, SECRET_KEY
    )
    return {
        "token": token,
        "id_usuario": u["id_usuario"],
        "nombre": u["nombre"],
        "nombre_rol": u["nombre_rol"],
    }


# ----------------------------------------------------------------------------
# ADMINISTRADOR: usuarios
# ----------------------------------------------------------------------------
@app.get("/api/admin/roles")
def listar_roles(_=Depends(solo_admin)):
    with get_cursor() as cur:
        cur.execute("SELECT id_rol, nombre_rol FROM roles ORDER BY id_rol")
        return cur.fetchall()


@app.get("/api/admin/usuarios")
def listar_usuarios(_=Depends(solo_admin)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id_usuario, u.nombre, u.email, u.id_rol, r.nombre_rol, u.fecha_creacion
               FROM usuarios u LEFT JOIN roles r ON u.id_rol = r.id_rol
               ORDER BY u.id_usuario"""
        )
        return cur.fetchall()


@app.post("/api/admin/usuarios")
def crear_usuario(usuario: NuevoUsuario, _=Depends(solo_admin)):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM roles WHERE id_rol = %s", (usuario.id_rol,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="El rol seleccionado no existe")
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, id_rol) VALUES (%s, %s, %s, %s)",
            (usuario.nombre.strip(), usuario.email.strip(), hash_password(usuario.password), usuario.id_rol),
        )
    return {"mensaje": "Usuario creado exitosamente"}


@app.put("/api/admin/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, datos: ActualizarUsuario, _=Depends(solo_admin)):
    nueva_clave = (datos.password or "").strip()
    if nueva_clave and len(nueva_clave) < 6:
        raise HTTPException(status_code=400, detail="La contrasena debe tener minimo 6 caracteres")
    with get_cursor() as cur:
        cur.execute(
            "SELECT r.nombre_rol FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol WHERE u.id_usuario = %s",
            (id_usuario,),
        )
        actual = cur.fetchone()
        if not actual:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        cur.execute("SELECT nombre_rol FROM roles WHERE id_rol = %s", (datos.id_rol,))
        nuevo = cur.fetchone()
        if not nuevo:
            raise HTTPException(status_code=400, detail="El rol seleccionado no existe")

        # Siempre debe quedar al menos un administrador
        if actual["nombre_rol"] == ADMIN and nuevo["nombre_rol"] != ADMIN:
            cur.execute(
                "SELECT COUNT(*) AS n FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol WHERE r.nombre_rol = %s",
                (ADMIN,),
            )
            if cur.fetchone()["n"] <= 1:
                raise HTTPException(status_code=400, detail="No puedes quitar el rol al unico administrador")

        if nueva_clave:
            cur.execute(
                "UPDATE usuarios SET nombre=%s, email=%s, id_rol=%s, password_hash=%s WHERE id_usuario=%s",
                (datos.nombre.strip(), datos.email.strip(), datos.id_rol, hash_password(nueva_clave), id_usuario),
            )
        else:
            cur.execute(
                "UPDATE usuarios SET nombre=%s, email=%s, id_rol=%s WHERE id_usuario=%s",
                (datos.nombre.strip(), datos.email.strip(), datos.id_rol, id_usuario),
            )
    return {"mensaje": "Usuario actualizado exitosamente"}


@app.delete("/api/admin/usuarios/{id_usuario}")
def eliminar_usuario(id_usuario: int, admin=Depends(solo_admin)):
    if id_usuario == admin["id_usuario"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    with get_cursor() as cur:
        # Sus movimientos del historial se conservan (id_usuario queda en NULL)
        cur.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"mensaje": "Usuario eliminado exitosamente"}


# ----------------------------------------------------------------------------
# ALMACENISTA (y Administrador): productos y entradas
# ----------------------------------------------------------------------------
@app.post("/api/almacen/productos")
def registrar_producto(p: NuevoProducto, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO productos (
                   codigo_barras,
                   nombre,
                   descripcion,
                   id_categoria,
                   id_proveedor,
                   precio_compra,
                   precio_venta,
                   stock_actual,
                   stock_minimo
               )
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                (p.codigo_barras or "").strip() or None,
                p.nombre.strip(),
                p.descripcion,
                p.id_categoria,
                p.id_proveedor,
                p.precio_compra,
                p.precio_venta,
                p.stock_actual,
                p.stock_minimo,
            ),
        )

    return {"mensaje": "Producto registrado exitosamente"}


@app.put("/api/almacen/productos/{id_producto}")
def editar_producto(id_producto: int, p: NuevoProducto, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """UPDATE productos
               SET codigo_barras=%s,
                   nombre=%s,
                   descripcion=%s,
                   id_categoria=%s,
                   id_proveedor=%s,
                   precio_compra=%s,
                   precio_venta=%s,
                   stock_actual=%s,
                   stock_minimo=%s
               WHERE id_producto=%s AND activo""",
            (
                (p.codigo_barras or "").strip() or None,
                p.nombre.strip(),
                p.descripcion,
                p.id_categoria,
                p.id_proveedor,
                p.precio_compra,
                p.precio_venta,
                p.stock_actual,
                p.stock_minimo,
                id_producto,
            ),
        )

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"mensaje": "Producto editado exitosamente"}

@app.delete("/api/almacen/productos/{id_producto}")
def borrar_producto(id_producto: int, _=Depends(almacen)):
    # Borrado logico: se conserva el historial para no alterar el total de ventas
    with get_cursor() as cur:
        cur.execute(
            "UPDATE productos SET activo = FALSE, codigo_barras = NULL WHERE id_producto=%s AND activo",
            (id_producto,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"mensaje": "Producto eliminado exitosamente"}


@app.post("/api/almacen/entradas")
def registrar_entrada(e: Entrada, usuario=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute("SELECT nombre FROM productos WHERE id_producto=%s AND activo", (e.id_producto,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        cur.execute(
            """INSERT INTO historial_inventario (id_producto, id_usuario, tipo_movimiento, cantidad, motivo)
               VALUES (%s, %s, 'ENTRADA', %s, %s)""",
            (e.id_producto, usuario["id_usuario"], e.cantidad, (e.motivo or "").strip() or "Entrada de mercancia"),
        )
    return {"mensaje": f"Entrada registrada: +{e.cantidad} de {prod['nombre']}"}


# ----------------------------------------------------------------------------
# VENDEDOR (y Administrador): salidas / ventas
# ----------------------------------------------------------------------------
@app.post("/api/ventas/registrar")
def registrar_salida(s: Salida, usuario=Depends(ventas)):
    with get_cursor() as cur:
        cur.execute(
            "SELECT nombre, precio_venta, stock_actual FROM productos WHERE id_producto=%s AND activo FOR UPDATE",
            (s.id_producto,),
        )
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        if prod["stock_actual"] < s.cantidad:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente: solo quedan {prod['stock_actual']} de {prod['nombre']}",
            )

        if s.tipo == "VENTA":
            precio = prod["precio_venta"]
            motivo = "Venta en mostrador"
        else:
            precio = None  # un retiro no suma al total vendido
            motivo = "Retiro: " + ((s.motivo or "").strip() or "sin motivo")

        cur.execute(
            """INSERT INTO historial_inventario
                   (id_producto, id_usuario, tipo_movimiento, cantidad, motivo, precio_unitario)
               VALUES (%s, %s, 'SALIDA', %s, %s, %s)""",
            (s.id_producto, usuario["id_usuario"], s.cantidad, motivo, precio),
        )

    if s.tipo == "VENTA":
        total = float(precio) * s.cantidad
        return {"mensaje": f"Venta registrada: {s.cantidad} x {prod['nombre']} = ${total:.2f}. Stock actualizado."}
    return {"mensaje": f"Retiro registrado: {s.cantidad} x {prod['nombre']}. Stock actualizado."}


@app.get("/api/ventas/total")
def obtener_total_ventas(_=Depends(ventas)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT COALESCE(SUM(cantidad * precio_unitario), 0) AS total,
                      COALESCE(SUM(cantidad), 0) AS unidades
               FROM historial_inventario
               WHERE tipo_movimiento = 'SALIDA' AND precio_unitario IS NOT NULL"""
        )
        r = cur.fetchone()
    return {"total_vendido": r["total"], "unidades_vendidas": int(r["unidades"])}


@app.get("/api/ventas/historial")
def historial_salidas(_=Depends(ventas)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT h.id_movimiento, h.fecha_movimiento, p.nombre AS producto, h.cantidad,
                      h.precio_unitario, (h.cantidad * h.precio_unitario) AS total,
                      CASE WHEN h.precio_unitario IS NULL THEN 'RETIRO' ELSE 'VENTA' END AS tipo,
                      u.nombre AS usuario
               FROM historial_inventario h
               JOIN productos p ON p.id_producto = h.id_producto
               LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario
               WHERE h.tipo_movimiento = 'SALIDA'
               ORDER BY h.fecha_movimiento DESC, h.id_movimiento DESC
               LIMIT 15"""
        )
        return cur.fetchall()


# ----------------------------------------------------------------------------
# Listados (requieren sesion)
# ----------------------------------------------------------------------------
@app.get("/api/productos/lista")
def listar_productos(usuario=Depends(usuario_actual)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT p.id_producto, p.codigo_barras, p.nombre, p.descripcion,
                      p.precio_compra, p.precio_venta, p.stock_actual, p.stock_minimo,
                      p.id_categoria, p.id_proveedor,
                      c.nombre AS categoria, pr.nombre_empresa AS proveedor
               FROM productos p
               LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
               LEFT JOIN proveedores pr ON p.id_proveedor = pr.id_proveedor
               WHERE p.activo
               ORDER BY p.nombre"""
        )
        filas = cur.fetchall()
    if usuario["rol"] == VENDEDOR:  # el vendedor no necesita ver costos ni proveedores
        for f in filas:
            f.pop("precio_compra", None)
            f.pop("proveedor", None)
            f.pop("id_proveedor", None)
    return filas


@app.get("/api/categorias/lista")
def listar_categorias(_=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute("SELECT id_categoria, nombre, descripcion FROM categorias ORDER BY nombre")
        return cur.fetchall()


@app.get("/api/proveedores/lista")
def listar_proveedores(_=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT id_proveedor, nombre_empresa, contacto_nombre, telefono, email, direccion
               FROM proveedores ORDER BY nombre_empresa"""
        )
        return cur.fetchall()


# ----------------------------------------------------------------------------
# ALMACEN / ADMIN: categorias, proveedores e historial de movimientos
# ----------------------------------------------------------------------------
class NuevaCategoria(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: Optional[str] = ""


class NuevoProveedor(BaseModel):
    nombre_empresa: str = Field(min_length=1, max_length=150)
    contacto_nombre: Optional[str] = ""
    telefono: Optional[str] = ""
    email: Optional[str] = ""
    direccion: Optional[str] = ""


@app.post("/api/almacen/categorias")
def crear_categoria(c: NuevaCategoria, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute("INSERT INTO categorias (nombre, descripcion) VALUES (%s, %s)", (c.nombre.strip(), c.descripcion))
    return {"mensaje": "Categoria creada"}


@app.put("/api/almacen/categorias/{id_categoria}")
def editar_categoria(id_categoria: int, c: NuevaCategoria, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE categorias SET nombre=%s, descripcion=%s WHERE id_categoria=%s",
            (c.nombre.strip(), c.descripcion, id_categoria),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Categoria no encontrada")
    return {"mensaje": "Categoria actualizada"}


@app.delete("/api/almacen/categorias/{id_categoria}")
def borrar_categoria(id_categoria: int, _=Depends(almacen)):
    # Los productos de esa categoria quedan "sin categoria" (ON DELETE SET NULL)
    with get_cursor() as cur:
        cur.execute("DELETE FROM categorias WHERE id_categoria=%s", (id_categoria,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Categoria no encontrada")
    return {"mensaje": "Categoria eliminada"}


@app.post("/api/almacen/proveedores")
def crear_proveedor(p: NuevoProveedor, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO proveedores (nombre_empresa, contacto_nombre, telefono, email, direccion)
               VALUES (%s, %s, %s, %s, %s)""",
            (p.nombre_empresa.strip(), p.contacto_nombre, p.telefono, p.email, p.direccion),
        )
    return {"mensaje": "Proveedor creado"}


@app.put("/api/almacen/proveedores/{id_proveedor}")
def editar_proveedor(id_proveedor: int, p: NuevoProveedor, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """UPDATE proveedores SET nombre_empresa=%s, contacto_nombre=%s, telefono=%s, email=%s, direccion=%s
               WHERE id_proveedor=%s""",
            (p.nombre_empresa.strip(), p.contacto_nombre, p.telefono, p.email, p.direccion, id_proveedor),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"mensaje": "Proveedor actualizado"}


@app.delete("/api/almacen/proveedores/{id_proveedor}")
def borrar_proveedor(id_proveedor: int, _=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute("DELETE FROM proveedores WHERE id_proveedor=%s", (id_proveedor,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"mensaje": "Proveedor eliminado"}


@app.get("/api/almacen/historial")
def historial_movimientos(_=Depends(almacen)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT h.id_movimiento, h.fecha_movimiento, p.nombre AS producto, h.tipo_movimiento,
                      h.cantidad, h.motivo, u.nombre AS usuario
               FROM historial_inventario h
               JOIN productos p ON p.id_producto = h.id_producto
               LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario
               ORDER BY h.fecha_movimiento DESC, h.id_movimiento DESC
               LIMIT 50"""
        )
        return cur.fetchall()
