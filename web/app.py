"""FastAPI application for Paper X-ray Web."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import models
import pdf_utils
import analyzer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
PDFS_DIR = DATA_DIR / "pdfs"


@asynccontextmanager
async def lifespan(app):
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    await models.init_db()
    log.info("Database initialized, PDF dir ready at %s", PDFS_DIR)
    yield


app = FastAPI(title="Paper X-ray Web", lifespan=lifespan)


# --- API Routes ---

@app.post("/api/upload")
async def upload_pdf(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    fingerprint = pdf_utils.compute_fingerprint(content)

    # Check for duplicate
    existing = await models.find_paper_by_fingerprint(fingerprint)
    if existing:
        return JSONResponse({
            "paper_id": existing["id"],
            "title": existing["title"],
            "is_duplicate": True,
        })

    paper_id = models.new_id()
    pdf_path = PDFS_DIR / f"{paper_id}.pdf"
    pdf_path.write_bytes(content)

    # Extract info
    try:
        text = pdf_utils.extract_text(pdf_path)
        page_count = pdf_utils.get_page_count(pdf_path)
        meta = pdf_utils.extract_metadata(pdf_path)
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Failed to process PDF: {e}")

    title = meta["title"] or file.filename.rsplit(".", 1)[0]
    authors = meta["authors"]

    paper = {
        "id": paper_id,
        "title": title,
        "authors": authors,
        "filename": file.filename,
        "pdf_path": str(pdf_path),
        "fingerprint": fingerprint,
        "text": text,
        "page_count": page_count,
        "created_at": models.now_iso(),
    }
    await models.insert_paper(paper)

    # Start background analysis
    await analyzer.start_all_analyses(paper_id)

    return JSONResponse({
        "paper_id": paper_id,
        "title": title,
        "is_duplicate": False,
    })


@app.get("/api/papers")
async def list_papers():
    papers = await models.list_papers()
    return papers


@app.delete("/api/papers/{paper_id}")
async def delete_paper(paper_id: str):
    paper = await models.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    # Delete PDF file
    pdf_path = Path(paper["pdf_path"])
    pdf_path.unlink(missing_ok=True)
    # Delete from DB
    await models.delete_paper(paper_id)
    return JSONResponse({"ok": True})


@app.get("/api/papers/{paper_id}")
async def get_paper(paper_id: str):
    paper = await models.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    # Don't send full text to client
    paper.pop("text", None)
    return paper


@app.get("/api/papers/{paper_id}/page/{page_num}")
async def get_page(paper_id: str, page_num: int):
    paper = await models.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")

    try:
        png_bytes = pdf_utils.render_page_png(paper["pdf_path"], page_num)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to render page: {e}")

    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/papers/{paper_id}/result")
async def get_result(paper_id: str, lang: str = "zh"):
    """SSE endpoint for analysis results. Streams if running, returns full if done."""
    paper = await models.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")

    result = await models.get_result(paper_id, lang)
    if not result:
        raise HTTPException(404, f"No analysis found for lang={lang}")

    if result["status"] == "done":
        return JSONResponse({"type": "complete", "content": result["content"]})

    if result["status"] == "error":
        return JSONResponse({"type": "error", "message": "Analysis failed"})

    # Stream progress for pending/running
    async def progress_stream():
        result_id = result["id"]
        last_len = 0
        while True:
            current = await models.get_result(paper_id, lang)
            if not current:
                break
            content = await models.get_result_content(result_id)
            if len(content) > last_len:
                new_chunk = content[last_len:]
                last_len = len(content)
                yield f"data: {_sse_json({'type': 'chunk', 'content': new_chunk})}\n\n"
            if current["status"] in ("done", "error"):
                yield f"data: {_sse_json({'type': 'status', 'status': current['status']})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(progress_stream(), media_type="text/event-stream")


@app.post("/api/papers/{paper_id}/chat")
async def chat(paper_id: str, request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(400, "Message is required")

    paper = await models.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")

    async def chat_stream():
        async for chunk in analyzer.stream_chat(paper_id, message):
            yield f"data: {_sse_json({'type': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {_sse_json({'type': 'done'})}\n\n"

    return StreamingResponse(chat_stream(), media_type="text/event-stream")


def _sse_json(obj: dict) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


# --- Static files (must be last) ---

app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8899)
