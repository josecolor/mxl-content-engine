from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import subprocess
import json
from datetime import datetime
from app.database import supabase

app = FastAPI(title="MXL Content Engine", version="1.0.0")

class JobCreate(BaseModel):
    url: HttpUrl
    niche: str
    screen: int

@app.get("/")
def read_root():
    return {"status": "online", "engine": "MXL Content Engine v1.0"}

@app.post("/api/jobs")
def create_job(job: JobCreate):
    # 1. Validar video con yt-dlp en tiempo real
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
                detail=f"URL de YouTube inválida o inaccesible por yt-dlp: {result.stderr[:200]}"
            )
            
        video_info = json.loads(result.stdout)
        video_title = video_info.get("title", "Desconocido")
        duration_seconds = video_info.get("duration", 0)
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="El tiempo de validación de yt-dlp expiró.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando yt-dlp: {str(e)}")

    # 2. Insertar el trabajo validado en la tabla jobs de Supabase
    job_data = {
        "url": str(job.url),
        "niche": job.niche,
        "screen": job.screen,
        "status": "pending",
        "video_title": video_title,
        "duration_seconds": duration_seconds,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    response = supabase.table("jobs").insert(job_data).execute()

    return {
        "message": "Trabajo creado y validado exitosamente",
        "job": response.data
    }
