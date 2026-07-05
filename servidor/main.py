import os
import shutil
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from servidor import database as db

# ─── CONFIGURACIÓN DE CANALES Y ESTADO ─────
CANALES_VALIDOS = [
    "#Importante",
    "#general",
    "#Conversacion 1",
    "#Conversacion 2",
    "#Conversacion 3",
    "#Conversacion 4",
    "#Eventos",
    "#Dudas",
    "#Regalos",
]

CHAT_ABIERTO = True

ALIAS_ADMIN = "Ful o´ Men"

conexiones_activas: Dict[str, List[WebSocket]] = {
    canal: [] for canal in CANALES_VALIDOS
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    print("[SERVIDOR] Base de datos inicializada")
    yield


app = FastAPI(title="Servidor Chat Secreto", lifespan=lifespan)

# ─── ENDPOINTS HTTP (LOGIN Y CONTROL) ─────


@app.post("/login")
def login(data: dict):
    """Verifica el código único de un amigo antes de dejarle entrar."""
    codigo = data.get("codigo")
    user = db.verificar_codigo(codigo)
    if not user:
        raise HTTPException(status_code=401, detail="Código secreto no válido.")

    user_id, alias = user
    return {
        "status": "success",
        "user_id": user_id,
        "alias": alias,
        "canales": CANALES_VALIDOS,
    }


@app.get("/historial/{canal}")
def obtener_historial(canal: str):
    """Devuelve los mensajes antiguos de un canal para que puedan leerlos."""
    if canal not in CANALES_VALIDOS:
        raise HTTPException(status_code=400, detail="Canal no válido.")
    return db.obtener_historial(canal)


# ─── CONTROL DE MODERACIÓN ─────
@app.post("/admin/toggle-chat")
def toggle_chat():
    """Cambia el estado del chat (Abre/Cierra la escritura)."""
    global CHAT_ABIERTO
    CHAT_ABIERTO = not CHAT_ABIERTO
    estado = "ABIERTO" if CHAT_ABIERTO else "CERRADO (Solo lectura)"
    print(f"[MODERACIÓN] El estado del chat ha cambiado a: {estado}")
    return {"status": "success", "chat_abierto": CHAT_ABIERTO}


@app.get("/admin/status")
def get_status():
    """Devuelve el estado actual del chat."""
    return {"chat_abierto": CHAT_ABIERTO}


# ─── MONTAR LA API ─────

# 1. Creamos una carpeta llamada 'uploads' dentro de 'servidor' si no existe
RUTA_UPLOADS = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(RUTA_UPLOADS, exist_ok=True)

# 2. Le decimos a FastAPI que cualquier archivo en esa carpeta sea accesible vía web
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)


# 3. Endpoint para recibir el archivo de amigos
@app.post("/upload-archivo")
async def subir_archivo(file: UploadFile = File(...)):
    nombre_original = file.filename or "archivo"
    nombre_limpio = nombre_original.replace(" ", "_")
    ruta_destino = os.path.join(RUTA_UPLOADS, nombre_limpio)

    with open(ruta_destino, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"url": f"/uploads/{nombre_limpio}", "nombre": nombre_limpio}


@app.get("/", response_class=HTMLResponse)
def servir_interfaz_web():
    ruta_html = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(ruta_html, "r", encoding="utf-8") as f:
        return f.read()


# ─── SISTEMA DE WEBSOCKETS (CHAT EN VIVO) ─────────────────────────────


@app.websocket("/ws/{canal}/{codigo}")
async def websocket_endpoint(websocket: WebSocket, canal: str, codigo: str):
    if canal not in CANALES_VALIDOS:
        await websocket.close(code=4000)
        return

    user = db.verificar_codigo(codigo)
    if not user:
        await websocket.close(code=4001)
        return

    user_id, alias = user
    await websocket.accept()

    conexiones_activas[canal].append(websocket)
    print(f"[CONEXIÓN] {alias} ha entrado al canal {canal}")

    try:
        while True:
            texto_mensaje = await websocket.receive_text()

            if canal == "#Importante" and alias != ALIAS_ADMIN:
                await websocket.send_json(
                    {
                        "sistema": True,
                        "contenido": "Error: Solo el administrador puede escribir en este canal.",
                    }
                )
                continue

            if not CHAT_ABIERTO:
                await websocket.send_json(
                    {
                        "sistema": True,
                        "contenido": "El chat está actualmente CERRADO por el moderador. Solo puedes leer.",
                    }
                )
                continue

            db.guardar_mensaje(user_id, canal, texto_mensaje)

            payload = {"sistema": False, "alias": alias, "contenido": texto_mensaje}

            for conexion in conexiones_activas[canal]:
                await conexion.send_json(payload)

    except WebSocketDisconnect:
        conexiones_activas[canal].remove(websocket)
        print(f"[DESCONEXIÓN] {alias} ha salido de {canal}")
