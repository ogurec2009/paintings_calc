from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List

from pack_paitings import DEFAULT_OFFSET, find_min_canvas_length  

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PaintingsInput(BaseModel):
    canvas_width: float
    paintings: List[List[float]]  
    offset: float = Field(default=DEFAULT_OFFSET, ge=0)  # отступ с каждой стороны, в сантиметрах

@app.post("/api/pack")
def pack(input_data: PaintingsInput):
    height, layout = find_min_canvas_length(input_data.canvas_width, input_data.paintings, input_data.offset)
    return {
        "canvas_length": height,
        "layout": layout
    }

