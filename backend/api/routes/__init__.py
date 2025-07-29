from fastapi import FastAPI
from backend.api.routes import models, documents, search, health, settings, ontology

app = FastAPI()
app.include_router(models.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(health.router)
app.include_router(settings.router)
app.include_router(ontology.router)