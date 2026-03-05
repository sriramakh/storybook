from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING_STORY = "generating_story"
    GENERATING_IMAGES = "generating_images"
    OVERLAYING_TEXT = "overlaying_text"
    COMPILING_PDF = "compiling_pdf"
    COMPLETED = "completed"
    FAILED = "failed"


class StoryGenerateRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=500, description="Story description/prompt")
    num_scenes: int = Field(12, ge=10, le=15, description="Number of scenes")
    animation_style: Optional[str] = Field(None, description="Animation style key")
    age_group: Optional[str] = Field("2-4", description="Target age group")


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: Optional[str] = None
    story_id: Optional[str] = None


class CharacterResponse(BaseModel):
    name: str
    type: str
    description: str


class SceneResponse(BaseModel):
    scene_number: int
    text: str
    background: str
    image_url: str


class StoryResponse(BaseModel):
    id: str
    title: str
    setting: str
    art_style: str
    moral: Optional[str] = None
    characters: list[CharacterResponse] = []
    scenes: list[SceneResponse] = []
    animation_style: Optional[str] = None
    created_at: str
    pdf_url: Optional[str] = None


class StoryListResponse(BaseModel):
    stories: list[StoryResponse]
    total: int
    page: int
    per_page: int


class StyleResponse(BaseModel):
    id: str
    name: str
    description: str


class StyleListResponse(BaseModel):
    styles: list[StyleResponse]
