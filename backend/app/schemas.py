from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str


class EMIRequest(BaseModel):
    principal: float = Field(gt=0)
    annual_rate: float = Field(gt=0)
    months: int = Field(gt=0)


class EMIResponse(BaseModel):
    emi: float
    total_payment: float
    total_interest: float


class ApplicationResponse(BaseModel):
    id: int
    client_id: int
    client_name: str
    client_email: str
    loan_type: str
    amount: float
    purpose: str
    documents: list[str]
    additional_documents: list[str]
    status: str
    admin_note: str
    requires_additional_docs: bool
    required_docs_note: str
    created_at: datetime


class UpdateStatusRequest(BaseModel):
    status: str
    admin_note: str = ""
    requires_additional_docs: bool = False
    required_docs_note: str = ""


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5)
    priority: str = Field(default="medium")


class TicketStatusUpdateRequest(BaseModel):
    status: str = Field(description="open|in_progress|resolved")


class TicketResponse(BaseModel):
    id: int
    owner_id: int
    owner_name: str
    owner_email: str
    assigned_admin_id: int | None
    assigned_admin_name: str | None
    subject: str
    message: str
    priority: str
    status: str
    created_by: str
    created_at: datetime


class PublicStatsResponse(BaseModel):
    total_applications: int
    approved_applications: int
    rejected_applications: int
    pending_applications: int
    approval_rate: float
    total_disbursed_amount: float


class PartnerResponse(BaseModel):
    name: str
    category: str


class ReviewResponse(BaseModel):
    customer_name: str
    product: str
    rating: int
    text: str


class FAQResponse(BaseModel):
    question: str
    answer: str


class TrafficResponse(BaseModel):
    total_api_events: int
    top_paths: list[dict[str, int]]
    role_breakdown: list[dict[str, int]]
    open_tickets: int
    resolved_tickets: int
    in_progress_tickets: int
