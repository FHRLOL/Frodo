import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class UserRole(str, Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"

class LabStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"

class ChatMode(str, Enum):
    SOCRATIC = "socratic"
    MASTER = "master"

# ----------------- User Models -----------------

class UserProfile(BaseModel):
    id: int
    moodle_user_id: str
    name: str
    email: Optional[str] = None
    role: UserRole
    created_at: Optional[str] = None

class UserCreate(BaseModel):
    moodle_user_id: str
    name: str
    email: Optional[str] = None
    role: UserRole = UserRole.STUDENT

# ----------------- Lab Models -----------------

class LabItem(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    order_num: int

class LabProgressItem(BaseModel):
    lab_id: int
    title: str
    description: Optional[str] = None
    order_num: int
    status: LabStatus
    grade: float = 0.0
    updated_at: Optional[str] = None
    can_master_mode: bool = False

class StudentProgressResponse(BaseModel):
    user: UserProfile
    labs: List[LabProgressItem]

class StudentMatrixItem(BaseModel):
    student: UserProfile
    labs: List[LabProgressItem]

class ProgressUpdateRequest(BaseModel):
    user_id: int
    lab_id: int
    status: LabStatus
    grade: Optional[float] = 0.0

# ----------------- Chat & Unanswered Models -----------------

class ChatMessageItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    lab_id: Optional[int] = None
    role: str
    content: str
    mode: ChatMode = ChatMode.SOCRATIC
    citations: Optional[str] = None
    score: Optional[float] = None
    created_at: Optional[str] = None

class UnansweredQueryItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    question: str
    score: Optional[float] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None

# ----------------- Auth / Token Models -----------------

class TokenPayload(BaseModel):
    sub: str  # user id
    moodle_user_id: str
    name: str
    email: Optional[str] = None
    role: str
    exp: int
