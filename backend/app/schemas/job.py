"""
Pydantic schemas for job-related endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class JobCreateRequest(BaseModel):
    """Request schema for creating a discovery job"""
    keywords: Optional[str] = Field(None, description="Search keywords (optional if categories provided)")
    locations: Optional[list[str]] = Field(None, description="Location filters (e.g., ['usa', 'canada'])")
    max_results: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    categories: Optional[list[str]] = Field(None, description="Category filters")


class JobResponse(BaseModel):
    """Response schema for job status"""
    id: UUID
    job_type: str
    status: str
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    drafts_created: int = Field(default=0)  # Progress tracking for drafting jobs (may not exist in DB)
    total_targets: Optional[int] = Field(default=None)  # Total targets for drafting jobs (may not exist in DB)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override to handle missing columns gracefully"""
        # Use getattr to safely access columns that may not exist
        data = {
            "id": obj.id,
            "job_type": obj.job_type,
            "status": obj.status,
            "params": getattr(obj, 'params', None),
            "result": getattr(obj, 'result', None),
            "error_message": getattr(obj, 'error_message', None),
            "drafts_created": getattr(obj, 'drafts_created', 0) or 0,
            "total_targets": getattr(obj, 'total_targets', None),
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


class JobStatusResponse(BaseModel):
    """Response schema for job status check"""
    id: UUID
    status: str
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class JobCreate(BaseModel):
    """Request schema for creating a job"""
    job_type: str
    params: Optional[Dict[str, Any]] = None


class JobListResponse(BaseModel):
    """Response schema for listing jobs"""
    data: List[JobResponse]
    total: int
    skip: int
    limit: int

