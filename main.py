from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI()

@app.get("/tasas")
def get_tasas():
    with open("data/tasas.json", "r", encoding="utf-8") as f:
        tasas = json.load(f)
    return tasas

# ✅ Hacer accesible la carpeta 'data'
app.mount("/data", StaticFiles(directory="data"), name="data")
