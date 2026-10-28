from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import subprocess
import json
from datetime import datetime, timezone
from app.database import supabase

app = FastAPI(
    title="MXL Content Engine",
    description="Backend para procesamiento y gestión de metadatos de video",
    version="1.0.0"
)

# Esquema de datos de entrada para la API
class JobCreate(BaseModel):
    url: HttpUrl
    niche: str
    screen: int


@app.get("/")
def read_root():
    return {
        "status": "online",
        "engine": "MXL Content Engine v1.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/jobs")
def create_job(job: JobCreate):
    # Validar que el parámetro screen esté dentro del rango permitido (1 a 4)
    if job.screen < 1 or job.screen > 4:
        raise HTTPException(
            status_code=400,
            detail="El campo 'screen' debe estar comprendido entre 1 y 4."
        )

    # 1. Obtener metadatos del video mediante yt-dlp
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        str(job.url)
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"URL inválida o inaccesible por yt-dlp: {result.stderr[:200]}"
            )

        video_info = json.loads(result.stdout)
        video_title = video_info.get("title", "Título no disponible")
        duration_seconds = video_info.get("duration", 0)

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Tiempo de espera agotado al consultar la información del video."
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Error al procesar la respuesta JSON de yt-dlp."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado durante la ejecución de yt-dlp: {str(e)}"
        )

    # 2. Mapear datos para la inserción en la tabla public.jobs de Supabase
    now_iso = datetime.now(timezone.utc).isoformat()
    
    job_data = {
        "url": str(job.url),
        "niche": job.niche,
        "screen": job.screen,
        "status": "pending",
        "video_title": video_title,
        "duration_seconds": duration_seconds,
        "error": None,
        "retries": 0,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    # 3. Insertar el registro en Supabase
    try:
        response = supabase.table("jobs").insert(job_data).execute()
        
        return {
            "message": "Trabajo creado y almacenado exitosamente",
            "job": response.data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar el registro en Supabase: {str(e)}"
        )
