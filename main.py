import uuid
from contextlib import asynccontextmanager
from typing import Union

import httpx
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import engine, init_db, get_db
from models import (
    CreateProfileRequest,
    ProfileResponse,
    ProfileSummaryResponse,
    CreateSuccessResponse,
    ExistingSuccessResponse,
    ListSuccessResponse,
    GetSuccessResponse,
    ErrorResponse,
    validate_uuid7,
)
from services import ExternalAPIService, ProfileService


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.http_client = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )
    yield
    await app.state.http_client.aclose()
    engine.dispose()


app = FastAPI(
    title="Backend Wizards Stage 1",
    description="Data Persistence & API Design Assessment",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# CRITICAL: Custom exception handler for correct 502 format
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Ensure error responses match spec: {status: error, message: ...}"""
    if isinstance(exc.detail, dict) and "status" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)}
    )


def validate_profile_id(profile_id: str) -> str:
    """Validate UUID v7 format - raises 422 if invalid."""
    if not validate_uuid7(profile_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Invalid UUID format"}
        )
    return profile_id


@app.post(
    "/api/profiles",
    response_model=Union[CreateSuccessResponse, ExistingSuccessResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
    tags=["Profiles"]
)
async def create_profile(
    request: CreateProfileRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    name = request.name
    
    try:
        existing = ProfileService.get_by_name(db, name)
        if existing:
            return ExistingSuccessResponse(
                status="success",
                message="Profile already exists",
                data=ProfileResponse.model_validate(existing)
            )
        
        api_service = ExternalAPIService(req.app.state.http_client)
        api_data = await api_service.fetch_all(name)
        api_data["name"] = name
        
        new_profile, already_existed = ProfileService.create(db, api_data)
        
        if already_existed:
            return ExistingSuccessResponse(
                status="success",
                message="Profile already exists",
                data=ProfileResponse.model_validate(new_profile)
            )
        
        return CreateSuccessResponse(
            status="success",
            data=ProfileResponse.model_validate(new_profile)
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Internal server error"}
        )


@app.get(
    "/api/profiles",
    response_model=ListSuccessResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["Profiles"]
)
async def get_all_profiles(
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    db: Session = Depends(get_db)
):
    try:
        profiles = ProfileService.get_all_filtered(db, gender, country_id, age_group)
        data = [ProfileSummaryResponse.model_validate(p) for p in profiles]
        
        return ListSuccessResponse(
            status="success",
            count=len(data),
            data=data
        )
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Internal server error"}
        )


@app.get(
    "/api/profiles/{profile_id}",
    response_model=GetSuccessResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    tags=["Profiles"]
)
async def get_profile(
    profile_id: str,
    db: Session = Depends(get_db)
):
    validate_profile_id(profile_id)
    
    profile = ProfileService.get_by_id(db, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "Profile not found"}
        )
    
    return GetSuccessResponse(
        status="success",
        data=ProfileResponse.model_validate(profile)
    )


@app.delete(
    "/api/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    tags=["Profiles"]
)
async def delete_profile(
    profile_id: str,
    db: Session = Depends(get_db)
):
    validate_profile_id(profile_id)
    
    profile = ProfileService.get_by_id(db, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "Profile not found"}
        )
    
    ProfileService.delete(db, profile)


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Backend Wizards Stage 1 API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
