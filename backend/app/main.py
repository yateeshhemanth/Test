import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .auth import create_access_token, decode_access_token, hash_password, verify_password
from .database import Base, engine, get_db
from .models import LoanApplication, Ticket, TrafficEvent, User
from .schemas import (
    EMIRequest,
    EMIResponse,
    ApplicationResponse,
    FAQResponse,
    LoginRequest,
    PartnerResponse,
    PublicStatsResponse,
    RegisterRequest,
    ReviewResponse,
    TicketCreateRequest,
    TicketResponse,
    TicketStatusUpdateRequest,
    TokenResponse,
    TrafficResponse,
    UpdateStatusRequest,
    UserResponse,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Loan Platform API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/frontend", StaticFiles(directory=str(ROOT / "frontend"), html=True), name="frontend")

PARTNERS = [
    {"name": "HDFC Bank", "category": "Banking Partner"},
    {"name": "ICICI Bank", "category": "Banking Partner"},
    {"name": "CIBIL", "category": "Credit Bureau"},
    {"name": "NSDL", "category": "KYC Infrastructure"},
    {"name": "Razorpay", "category": "Payments"},
    {"name": "AWS", "category": "Cloud Infrastructure"},
]

REVIEWS = [
    {
        "customer_name": "Ananya Sharma",
        "product": "Home Loan",
        "rating": 5,
        "text": "Sanctioned quickly, transparent process and dedicated relationship manager.",
    },
    {
        "customer_name": "Rahul Nair",
        "product": "Business Loan",
        "rating": 5,
        "text": "The dashboard gave complete visibility and helped us track every stage.",
    },
    {
        "customer_name": "Meera Iyer",
        "product": "Personal Loan",
        "rating": 4,
        "text": "Great support team and very easy documentation flow.",
    },
]

FAQS = [
    {
        "question": "How long does loan approval take?",
        "answer": "Most applications are reviewed within 24-72 hours depending on document quality and profile checks.",
    },
    {
        "question": "Can I track my loan status in real time?",
        "answer": "Yes. After login, go to dashboard > My Applications to view live status updates.",
    },
    {
        "question": "What documents are mandatory?",
        "answer": "ID proof, address proof, and income proof are required for all retail products.",
    },
    {
        "question": "How are tickets assigned?",
        "answer": "Tickets are auto-assigned to active admin users by least-load allocation.",
    },
]


def run_lightweight_migrations() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE loan_applications ADD COLUMN additional_documents TEXT DEFAULT '[]'"))


def safe_alter(statement: str) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except Exception:
        pass


@app.on_event("startup")
def startup_setup() -> None:
    # Compatibility for existing local sqlite DB without full migration tool
    safe_alter("ALTER TABLE loan_applications ADD COLUMN additional_documents TEXT DEFAULT '[]'")
    safe_alter("ALTER TABLE loan_applications ADD COLUMN requires_additional_docs TEXT DEFAULT 'false'")
    safe_alter("ALTER TABLE loan_applications ADD COLUMN required_docs_note TEXT DEFAULT ''")
    safe_alter("ALTER TABLE tickets ADD COLUMN assigned_admin_id INTEGER")
    safe_alter("ALTER TABLE tickets ADD COLUMN priority TEXT DEFAULT 'medium'")
    safe_alter("ALTER TABLE tickets ADD COLUMN status TEXT DEFAULT 'open'")

    db = next(get_db())
    try:
        if not db.query(User).filter(User.email == "admin@incred.local").first():
            db.add(
                User(
                    name="Platform Admin",
                    email="admin@incred.local",
                    password_hash=hash_password("admin123"),
                    role="admin",
                )
            )
        if not db.query(User).filter(User.email == "superadmin@incred.local").first():
            db.add(
                User(
                    name="Super Admin",
                    email="superadmin@incred.local",
                    password_hash=hash_password("superadmin123"),
                    role="super_admin",
                )
            )
        db.commit()
    finally:
        db.close()


@app.middleware("http")
async def track_traffic(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        actor_role = "anonymous"
        actor_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            subject = decode_access_token(auth_header.split(" ", 1)[1])
            if subject:
                db = next(get_db())
                try:
                    user = db.query(User).filter(User.id == int(subject)).first()
                    if user:
                        actor_role = user.role
                        actor_id = user.id
                finally:
                    db.close()

        db = next(get_db())
        try:
            db.add(
                TrafficEvent(
                    path=request.url.path,
                    method=request.method,
                    actor_role=actor_role,
                    actor_id=actor_id,
                )
            )
            db.commit()
        finally:
            db.close()
    return response


def get_current_user(
    authorization: str = Header(default=""), db: Session = Depends(get_db)
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    subject = decode_access_token(token)
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(subject)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def serialize_app(row: LoanApplication) -> ApplicationResponse:
    return ApplicationResponse(
        id=row.id,
        client_id=row.client_id,
        client_name=row.client.name,
        client_email=row.client.email,
        loan_type=row.loan_type,
        amount=row.amount,
        purpose=row.purpose,
        documents=json.loads(row.documents or "[]"),
        additional_documents=json.loads(row.additional_documents or "[]"),
        status=row.status,
        admin_note=row.admin_note,
        requires_additional_docs=(row.requires_additional_docs == "true"),
        required_docs_note=row.required_docs_note,
        created_at=row.created_at,
    )


def serialize_ticket(row: Ticket) -> TicketResponse:
    assigned_name = row.assigned_admin.name if row.assigned_admin else None
    return TicketResponse(
        id=row.id,
        owner_id=row.owner_id,
        owner_name=row.owner.name,
        owner_email=row.owner.email,
        assigned_admin_id=row.assigned_admin_id,
        assigned_admin_name=assigned_name,
        subject=row.subject,
        message=row.message,
        priority=row.priority,
        status=row.status,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def get_least_loaded_admin_id(db: Session) -> int | None:
    admins = db.query(User).filter(User.role.in_(["admin", "super_admin"])) .all()
    if not admins:
        return None

    ticket_counts = {
        admin.id: db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_admin_id == admin.id,
            Ticket.status.in_(["open", "in_progress"]),
        ).scalar()
        or 0
        for admin in admins
    }
    return min(ticket_counts, key=ticket_counts.get)


def create_system_ticket(db: Session, owner_id: int, subject: str, message: str) -> None:
    assigned_admin_id = get_least_loaded_admin_id(db)
    db.add(
        Ticket(
            owner_id=owner_id,
            subject=subject,
            message=message,
            created_by="system",
            assigned_admin_id=assigned_admin_id,
            priority="medium",
            status="open",
        )
    )


@app.get("/")
def root() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/api/public/partners", response_model=list[PartnerResponse])
def partners() -> list[PartnerResponse]:
    return [PartnerResponse(**partner) for partner in PARTNERS]


@app.get("/api/public/reviews", response_model=list[ReviewResponse])
def reviews() -> list[ReviewResponse]:
    return [ReviewResponse(**review) for review in REVIEWS]


@app.get("/api/public/faqs", response_model=list[FAQResponse])
def faqs() -> list[FAQResponse]:
    return [FAQResponse(**faq) for faq in FAQS]


@app.get("/api/public/stats", response_model=PublicStatsResponse)
def public_stats(db: Session = Depends(get_db)) -> PublicStatsResponse:
    total = db.query(func.count(LoanApplication.id)).scalar() or 0
    approved = (
        db.query(func.count(LoanApplication.id))
        .filter(LoanApplication.status == "Approved")
        .scalar()
        or 0
    )
    rejected = (
        db.query(func.count(LoanApplication.id))
        .filter(LoanApplication.status == "Rejected")
        .scalar()
        or 0
    )
    pending = max(total - approved - rejected, 0)
    disbursed = (
        db.query(func.sum(LoanApplication.amount))
        .filter(LoanApplication.status == "Approved")
        .scalar()
        or 0.0
    )
    rate = round((approved / total) * 100, 2) if total else 0.0
    return PublicStatsResponse(
        total_applications=total,
        approved_applications=approved,
        rejected_applications=rejected,
        pending_applications=pending,
        approval_rate=rate,
        total_disbursed_amount=float(disbursed),
    )


@app.post("/api/auth/register", response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    exists = db.query(User).filter(User.email == payload.email.lower()).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="client",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role)


@app.post("/api/emi/calculate", response_model=EMIResponse)
def emi(payload: EMIRequest) -> EMIResponse:
    monthly = payload.annual_rate / 12 / 100
    factor = (1 + monthly) ** payload.months
    emi_val = (payload.principal * monthly * factor) / (factor - 1)
    total = emi_val * payload.months
    return EMIResponse(emi=emi_val, total_payment=total, total_interest=total - payload.principal)


@app.post("/api/contact")
def contact_submission(name: str = Form(...), email: str = Form(...), message: str = Form(...)) -> dict[str, str]:
    if len(message.strip()) < 10:
        raise HTTPException(status_code=400, detail="Message too short")
    return {"status": "received", "message": f"Thank you {name}, our team will reach out at {email}."}


@app.post("/api/applications", response_model=ApplicationResponse)
def create_application(
    loan_type: str = Form(...),
    amount: float = Form(...),
    purpose: str = Form(...),
    id_proof: UploadFile = File(...),
    income_proof: UploadFile = File(...),
    address_proof: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationResponse:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can apply")

    files = [id_proof, income_proof, address_proof]
    stored_names: list[str] = []
    for f in files:
        clean_name = (f.filename or "file").replace("/", "_").replace("\\", "_")
        filename = f"{user.id}_{clean_name}"
        target = UPLOAD_DIR / filename
        target.write_bytes(f.file.read())
        stored_names.append(filename)

    app_row = LoanApplication(
        client_id=user.id,
        loan_type=loan_type,
        amount=amount,
        purpose=purpose,
        documents=json.dumps(stored_names),
        additional_documents="[]",
        status="Pending",
        admin_note="",
        requires_additional_docs="false",
        required_docs_note="",
    )
    db.add(app_row)
    create_system_ticket(
        db,
        user.id,
        "Application Submitted",
        f"Your {loan_type} request is submitted and pending admin review.",
    )
    db.commit()
    db.refresh(app_row)
    return serialize_app(app_row)


@app.post("/api/applications/{application_id}/additional-documents", response_model=ApplicationResponse)
def upload_additional_documents(
    application_id: int,
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationResponse:
    row = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    if row.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can upload additional documents")

    extra = json.loads(row.additional_documents or "[]")
    clean_name = (document.filename or "additional_file").replace("/", "_").replace("\\", "_")
    filename = f"{user.id}_extra_{clean_name}"
    (UPLOAD_DIR / filename).write_bytes(document.file.read())
    extra.append(filename)
    row.additional_documents = json.dumps(extra)
    row.requires_additional_docs = "false"
    row.required_docs_note = ""

    create_system_ticket(
        db,
        user.id,
        "Additional Document Uploaded",
        f"Client uploaded additional document for application #{row.id}.",
    )
    db.commit()
    db.refresh(row)
    return serialize_app(row)


@app.get("/api/applications/my", response_model=list[ApplicationResponse])
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationResponse]:
    rows = (
        db.query(LoanApplication)
        .filter(LoanApplication.client_id == user.id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )
    return [serialize_app(row) for row in rows]


@app.get("/api/applications", response_model=list[ApplicationResponse])
def all_applications(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ApplicationResponse]:
    rows = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).all()
    return [serialize_app(row) for row in rows]


@app.patch("/api/applications/{application_id}", response_model=ApplicationResponse)
def update_application_status(
    application_id: int,
    payload: UpdateStatusRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    if payload.status not in {"Approved", "Rejected", "Pending"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    row = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    row.status = payload.status
    row.admin_note = f"{payload.admin_note} (updated by {admin.name})".strip()
    row.requires_additional_docs = "true" if payload.requires_additional_docs else "false"
    row.required_docs_note = payload.required_docs_note

    create_system_ticket(
        db,
        row.client_id,
        f"Application {payload.status}",
        f"Your {row.loan_type} application is marked as {payload.status}. {payload.required_docs_note}",
    )
    db.commit()
    db.refresh(row)
    return serialize_app(row)


@app.post("/api/tickets", response_model=TicketResponse)
def create_ticket(
    payload: TicketCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketResponse:
    assigned_admin_id = get_least_loaded_admin_id(db)
    ticket = Ticket(
        owner_id=user.id,
        subject=payload.subject,
        message=payload.message,
        created_by=user.role,
        assigned_admin_id=assigned_admin_id,
        priority=payload.priority,
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(ticket)


@app.patch("/api/tickets/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TicketResponse:
    if payload.status not in {"open", "in_progress", "resolved"}:
        raise HTTPException(status_code=400, detail="Invalid ticket status")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(ticket)


@app.get("/api/tickets/my", response_model=list[TicketResponse])
def my_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TicketResponse]:
    rows = db.query(Ticket).filter(Ticket.owner_id == user.id).order_by(Ticket.created_at.desc()).all()
    return [serialize_ticket(row) for row in rows]


@app.get("/api/tickets", response_model=list[TicketResponse])
def all_tickets(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[TicketResponse]:
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return [serialize_ticket(row) for row in rows]


@app.get("/api/super-admin/traffic", response_model=TrafficResponse)
def traffic_analytics(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> TrafficResponse:
    total = db.query(func.count(TrafficEvent.id)).scalar() or 0

    path_rows = (
        db.query(TrafficEvent.path, func.count(TrafficEvent.id).label("count"))
        .group_by(TrafficEvent.path)
        .order_by(func.count(TrafficEvent.id).desc())
        .limit(8)
        .all()
    )
    role_rows = (
        db.query(TrafficEvent.actor_role, func.count(TrafficEvent.id).label("count"))
        .group_by(TrafficEvent.actor_role)
        .order_by(func.count(TrafficEvent.id).desc())
        .all()
    )

    open_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "open").scalar() or 0
    in_progress_tickets = (
        db.query(func.count(Ticket.id)).filter(Ticket.status == "in_progress").scalar() or 0
    )
    resolved_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "resolved").scalar() or 0

    return TrafficResponse(
        total_api_events=total,
        top_paths=[{"path": path, "count": count} for path, count in path_rows],
        role_breakdown=[{"role": role, "count": count} for role, count in role_rows],
        open_tickets=open_tickets,
        resolved_tickets=resolved_tickets,
        in_progress_tickets=in_progress_tickets,
    )
