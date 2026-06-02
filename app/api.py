import sys
import subprocess
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import threading
import traceback

app = FastAPI()

# Allow CORS so React (port 5173) can talk to this API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BotRequest(BaseModel):
    ruc: str
    periodo: str | None = None

# Store references to running tasks to prevent overlapping
running_tasks = {}

# Ensure logs directory exists
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def _run_sync_process(task_id: str, command: list, cwd: str):
    log_file = LOGS_DIR / f"{task_id}.log"
    # Overwrite the log file for each new execution of the same task_id
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"[{task_id}] Starting command: {' '.join(command)}\n")
        print(f"[{task_id}] Starting command: {' '.join(command)}")
        
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            for line in process.stdout:
                # Write to file and print to console
                f.write(line)
                f.flush()
                print(f"[{task_id}] {line.strip()}")
                
            process.wait()
            f.write(f"[{task_id}] Finished with return code {process.returncode}\n")
            print(f"[{task_id}] Finished with return code {process.returncode}")
        except Exception as e:
            err_trace = traceback.format_exc()
            f.write(f"[{task_id}] Failed to run command: {e}\n{err_trace}\n")
            print(f"[{task_id}] Failed to run command: {e}")
            print(err_trace)
        finally:
            if task_id in running_tasks:
                del running_tasks[task_id]

async def run_command_in_background(task_id: str, command: list, cwd: str):
    thread = threading.Thread(target=_run_sync_process, args=(task_id, command, cwd))
    thread.daemon = True
    thread.start()

@app.post("/api/bot/download-api")
async def trigger_download_api(req: BotRequest, background_tasks: BackgroundTasks):
    if not req.ruc or not req.periodo:
        raise HTTPException(status_code=400, detail="RUC and Periodo are required")
        
    task_id = f"api_{req.ruc}_{req.periodo}"
    if task_id in running_tasks:
        return {"status": "already_running", "message": "This API task is already running.", "task_id": task_id}
        
    cmd = [sys.executable, "app/brain/sire_download_cli.py", "--client", req.ruc, "--period", req.periodo]
    root_dir = Path(__file__).parent.parent
    
    running_tasks[task_id] = True
    background_tasks.add_task(run_command_in_background, task_id, cmd, str(root_dir))
    return {"status": "started", "message": f"Started SIRE API Download for {req.ruc} - {req.periodo}", "task_id": task_id}

@app.post("/api/bot/automation-login")
async def trigger_automation_login(req: BotRequest, background_tasks: BackgroundTasks):
    if not req.ruc:
        raise HTTPException(status_code=400, detail="RUC is required")
        
    task_id = f"login_{req.ruc}"
    if task_id in running_tasks:
        return {"status": "already_running", "message": "Login task is already running.", "task_id": task_id}
        
    cmd = [sys.executable, "app/brain/automation_scraper.py", "--ruc", req.ruc]
    root_dir = Path(__file__).parent.parent
    
    running_tasks[task_id] = True
    background_tasks.add_task(run_command_in_background, task_id, cmd, str(root_dir))
    return {"status": "started", "message": f"Started Authentication bot for {req.ruc}", "task_id": task_id}

@app.post("/api/bot/download-fisicos")
async def trigger_download_fisicos(req: BotRequest, background_tasks: BackgroundTasks):
    if not req.ruc:
        raise HTTPException(status_code=400, detail="RUC is required")
        
    task_id = f"fisicos_{req.ruc}"
    if task_id in running_tasks:
        return {"status": "already_running", "message": "XML Scraper is already running.", "task_id": task_id}
        
    cmd = [sys.executable, "app/brain/db/sire_bot_orchestrator.py", "--limit", "200", "--ruc", req.ruc]
    root_dir = Path(__file__).parent.parent
    
    running_tasks[task_id] = True
    background_tasks.add_task(run_command_in_background, task_id, cmd, str(root_dir))
    return {"status": "started", "message": f"Started XML Download bot for {req.ruc}", "task_id": task_id}

@app.post("/api/bot/enrich-xml")
async def trigger_enrich_xml(req: BotRequest, background_tasks: BackgroundTasks):
    if not req.ruc:
        raise HTTPException(status_code=400, detail="RUC is required")
        
    task_id = f"enrich_{req.ruc}"
    if task_id in running_tasks:
        return {"status": "already_running", "message": "XML Enricher is already running.", "task_id": task_id}
        
    cmd = [sys.executable, "app/brain/db/sire_xml_enricher.py", "--limit", "500", "--ruc", req.ruc]
    root_dir = Path(__file__).parent.parent
    
    running_tasks[task_id] = True
    background_tasks.add_task(run_command_in_background, task_id, cmd, str(root_dir))
    return {"status": "started", "message": f"Started XML Extraction bot for {req.ruc}", "task_id": task_id}

@app.post("/api/bot/classify-ai")
async def trigger_classify_ai(req: BotRequest, background_tasks: BackgroundTasks):
    if not req.ruc:
        raise HTTPException(status_code=400, detail="RUC is required")
        
    task_id = f"classify_{req.ruc}"
    if task_id in running_tasks:
        return {"status": "already_running", "message": "AI Classifier is already running.", "task_id": task_id}
        
    cmd = [sys.executable, "app/brain/db/ai_classifier.py", "--limit", "100", "--ruc", req.ruc]
    root_dir = Path(__file__).parent.parent
    
    running_tasks[task_id] = True
    background_tasks.add_task(run_command_in_background, task_id, cmd, str(root_dir))
    return {"status": "started", "message": f"Started AI Classification bot for {req.ruc}", "task_id": task_id}

@app.get("/api/bot/logs/{task_id}")
def get_task_logs(task_id: str):
    log_file = LOGS_DIR / f"{task_id}.log"
    if not log_file.exists():
        return {"task_id": task_id, "logs": "No logs available yet..."}
    
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        # For huge files, we should probably read the last N lines, but for these bots it should be fine.
        content = f.read()

    return {"task_id": task_id, "logs": content}
    
import os
import tempfile
import fitz  # PyMuPDF
from fastapi.responses import FileResponse
from app.brain.db.supabase_client import get_supabase

class ExportPdfRequest(BaseModel):
    ruc: str
    periodo: str
    tipo_libro: str
    allow_incomplete: bool = False

def _safe_remove_file(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        # Best-effort cleanup; avoid surfacing Windows file-lock errors.
        pass

@app.post("/api/export/pdf-merged")
def export_pdf_merged(req: ExportPdfRequest, background_tasks: BackgroundTasks):
    supabase = get_supabase()
    
    # Obtener el id del cliente
    res_cli = supabase.table("clientes").select("id").eq("ruc", req.ruc).execute()
    if not res_cli.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente_id = res_cli.data[0]["id"]
    
    # Obtener las rutas de los pdf y datos del comprobante de ese cliente, periodo y tipo
    res_docs = supabase.table("sire_comprobantes_fisicos").select("id, serie, numero, ruta_pdf").eq("cliente_id", cliente_id).eq("periodo", req.periodo).eq("tipo_libro", req.tipo_libro).execute()
    
    if not res_docs.data:
        raise HTTPException(status_code=404, detail="No hay comprobantes para exportar")
        
    comprobantes = res_docs.data
    failed_comprobantes = []
    
    try:
        merged_doc = fitz.open()
        for comp in comprobantes:
            pdf_path = comp.get("ruta_pdf")
            serie = comp.get("serie", "N/A")
            numero = comp.get("numero", "N/A")
            
            if not pdf_path or not os.path.exists(pdf_path):
                failed_comprobantes.append(comp)
                continue
                
            try:
                doc = fitz.open(pdf_path)
                merged_doc.insert_pdf(doc)
                doc.close()
            except Exception as e:
                print(f"Error merging {pdf_path}: {e}")
                failed_comprobantes.append(comp)
                
        # Si todos fallaron, no hay nada que compilar
        if len(failed_comprobantes) == len(comprobantes):
            merged_doc.close()
            raise HTTPException(status_code=400, detail="Ningún comprobante tiene un PDF válido o descargado para compilar.")
            
        # Si hubo comprobantes que fallaron y NO se permite incompleto, abortar
        if failed_comprobantes and not req.allow_incomplete:
            merged_doc.close()
            failed_names = []
            
            for fcomp in failed_comprobantes:
                failed_names.append(f"{fcomp.get('serie')}-{fcomp.get('numero')}")
                # Actualizar a PENDIENTE para que el bot vuelva a intentarlo
                supabase.table("sire_comprobantes_fisicos").update({
                    "estado_xml": "PENDIENTE",
                    "estado_pdf": "PENDIENTE",
                    "reintentos": 0
                }).eq("id", fcomp["id"]).execute()
            
            error_msg = f"No se pudo generar el compilado PDF porque los siguientes comprobantes no se descargaron correctamente o están corruptos: {', '.join(failed_names)}. Se han devuelto a estado PENDIENTE."
            raise HTTPException(status_code=400, detail=error_msg)
            
        # Si se permite incompleto, solo marcar los fallidos como PENDIENTE sin abortar
        if failed_comprobantes and req.allow_incomplete:
            for fcomp in failed_comprobantes:
                supabase.table("sire_comprobantes_fisicos").update({
                    "estado_pdf": "PENDIENTE",
                    "reintentos": 0
                }).eq("id", fcomp["id"]).execute()

        # Guardar en un archivo temporal si todo está correcto
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        merged_doc.save(tmp.name)
        merged_doc.close()
        
        filename = f"Comprobantes_{req.tipo_libro}_{req.periodo}.pdf"
        background_tasks.add_task(_safe_remove_file, tmp.name)
        return FileResponse(tmp.name, filename=filename, media_type="application/pdf")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bot/sync-files")
def sync_files_api():
    try:
        # Run sync_files.py synchronously and capture output
        cmd = [sys.executable, "app/brain/db/sync_files.py"]
        root_dir = Path(__file__).parent.parent
        result = subprocess.run(cmd, cwd=str(root_dir), capture_output=True, text=True, encoding='utf-8')
        return {"status": "ok", "message": "Archivos sincronizados", "output": result.stdout}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "running_tasks": list(running_tasks.keys())}
