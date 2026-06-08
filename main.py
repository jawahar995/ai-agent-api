from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import Request
import json

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_path(request: Request, call_next):
    print("Request path:", request.url.path)
    response = await call_next(request)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        errors = [
        {"field": ".".join(map(str, err["loc"])), "error": err["msg"]}
        for err in exc.errors()
        ]
        return JSONResponse(
        status_code=422,
        content={"message": "Invalid input data", "errors": errors,}
        )
    except Exception as e:
        return JSONResponse(status_code = 400, content = {"message":"Invalid JSON format"})
@app.exception_handler(json.JSONDecodeError)
async def json_decode_error_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(status_code = 400, content = {"message":"Invalid JSON format"})


from src.routes import init_routes
init_routes(app)