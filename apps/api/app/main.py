from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.api_schemas import (
    ApplicationDetail,
    ApplicationRead,
    EmailDetail,
    EmailRead,
    ErrorResponse,
    EventRead,
    HealthResponse,
    ProcessEmailResponse,
    TaskRead,
)
from apps.api.app.config import Settings, get_settings
from apps.api.app.database import create_engine, create_session_factory
from apps.api.app.logging_config import configure_logging
from apps.api.app.models import Application, ApplicationEvent, Email, Task
from apps.api.app.service import (
    EmailProcessingService,
    IdempotencyConflictError,
    ProcessingFailedError,
)
from packages.llm.fixture import FixtureEmailIntelligenceProvider
from packages.llm.provider import EmailIntelligenceProvider
from packages.schemas.email import EmailInput


def create_app(
    settings: Settings | None = None,
    provider: EmailIntelligenceProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    engine = create_engine(resolved_settings.database_url)
    sessions = session_factory or create_session_factory(engine)
    resolved_provider = provider or FixtureEmailIntelligenceProvider()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        yield
        await engine.dispose()

    app = FastAPI(
        title="InboxOS API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.sessions = sessions
    app.state.processing_service = EmailProcessingService(sessions, resolved_provider)

    @app.get("/healthz", response_model=HealthResponse, tags=["system"])
    async def health(request: Request) -> HealthResponse:
        async with request.app.state.sessions() as session:
            await session.execute(text("SELECT 1"))
        return HealthResponse(status="ok")

    @app.post(
        "/api/emails/process",
        response_model=ProcessEmailResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            409: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
        tags=["emails"],
    )
    async def process_email(
        payload: EmailInput,
        response: Response,
        request: Request,
        idempotency_key: str = Header(
            min_length=1,
            max_length=128,
            alias="Idempotency-Key",
        ),
    ) -> ProcessEmailResponse | JSONResponse:
        service: EmailProcessingService = request.app.state.processing_service
        try:
            outcome = await service.process(payload, idempotency_key)
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ProcessingFailedError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": "Email processing failed", "trace_id": str(exc.trace_id)},
            )
        if outcome.replayed:
            response.status_code = status.HTTP_200_OK
        return outcome.response

    @app.get("/api/emails/{email_id}", response_model=EmailDetail, tags=["emails"])
    async def get_email(email_id: UUID, request: Request) -> EmailDetail:
        async with request.app.state.sessions() as session:
            email = await session.get(Email, email_id)
            if email is None:
                raise HTTPException(status_code=404, detail="Email not found")
            return EmailDetail.model_validate(email)

    @app.get("/api/applications", response_model=list[ApplicationRead], tags=["applications"])
    async def list_applications(request: Request) -> list[ApplicationRead]:
        async with request.app.state.sessions() as session:
            applications = await session.scalars(
                select(Application).order_by(Application.updated_at.desc())
            )
            return [ApplicationRead.model_validate(item) for item in applications]

    @app.get(
        "/api/applications/{application_id}",
        response_model=ApplicationDetail,
        tags=["applications"],
    )
    async def get_application(application_id: UUID, request: Request) -> ApplicationDetail:
        async with request.app.state.sessions() as session:
            application = await session.get(Application, application_id)
            if application is None:
                raise HTTPException(status_code=404, detail="Application not found")
            emails = list(
                await session.scalars(
                    select(Email)
                    .where(Email.application_id == application_id)
                    .order_by(Email.received_at.desc())
                )
            )
            events = list(
                await session.scalars(
                    select(ApplicationEvent)
                    .where(ApplicationEvent.application_id == application_id)
                    .order_by(ApplicationEvent.event_date.desc())
                )
            )
            tasks = list(
                await session.scalars(
                    select(Task)
                    .where(Task.application_id == application_id)
                    .order_by(Task.created_at.desc())
                )
            )
            base = ApplicationRead.model_validate(application).model_dump()
            return ApplicationDetail(
                **base,
                emails=[EmailRead.model_validate(item) for item in emails],
                events=[EventRead.model_validate(item) for item in events],
                tasks=[TaskRead.model_validate(item) for item in tasks],
            )

    return app


app = create_app()
