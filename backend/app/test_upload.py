from fastapi import FastAPI, File, UploadFile

app = FastAPI(multipart_params={"max_part_size": 50 * 1024 * 1024})

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    return {"filename": file.filename}