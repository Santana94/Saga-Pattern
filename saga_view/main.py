import logging
from fastapi import FastAPI, HTTPException, Query
from saga_view.settings import lifespan
from saga_view.models import sagas, saga_events, SessionLocal
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Saga view main.py loading...")

app = FastAPI(title="SAGA View Service - Choreographed SAGA Monitor", lifespan=lifespan)

logger.info("FastAPI app created with lifespan")

class SagaEvent(BaseModel):
    id: int
    event_type: str
    service: str
    event_data: dict
    timestamp: datetime
    sequence: int

class DetailedSagaView(BaseModel):
    saga_id: str
    order_id: Optional[int]
    order_status: Optional[str]
    payment_status: Optional[str]
    delivery_status: Optional[str]
    saga_status: str
    item: Optional[str]
    quantity: Optional[int]
    price: Optional[float]
    created_at: datetime
    updated_at: datetime
    completion_reason: Optional[str]
    error_message: Optional[str]
    total_events: Optional[int] = 0

class SagaSummary(BaseModel):
    saga_id: str
    order_id: Optional[int]
    saga_status: str
    item: Optional[str]
    price: Optional[float]
    created_at: datetime
    completion_reason: Optional[str]

class SagaTimeline(BaseModel):
    saga: DetailedSagaView
    events: List[SagaEvent]

class SagaStats(BaseModel):
    total_sagas: int
    completed: int
    failed: int
    compensated: int
    in_progress: int
    started: int
    success_rate: float

@app.get("/")
async def health_check():
    return {
        "service": "saga_view", 
        "status": "healthy",
        "description": "Choreographed SAGA View Service"
    }

@app.get("/sagas", response_model=List[SagaSummary])
def get_all_sagas(
    status: Optional[str] = Query(None, description="Filter by saga status"),
    limit: int = Query(50, description="Maximum number of sagas to return"),
    offset: int = Query(0, description="Number of sagas to skip")
):
    """Get a list of all sagas with optional filtering"""
    db = SessionLocal()
    try:
        query = sagas.select().order_by(sagas.c.created_at.desc())
        
        if status:
            query = query.where(sagas.c.saga_status == status)
            
        query = query.limit(limit).offset(offset)
        results = db.execute(query).fetchall()
        
        saga_list = []
        for row in results:
            saga_list.append(SagaSummary(
                saga_id=row[1],  # saga_id
                order_id=row[2],  # order_id
                saga_status=row[6] or "started",  # saga_status
                item=row[7],  # item
                price=row[9],  # price
                created_at=row[10],  # created_at
                completion_reason=row[12]  # completion_reason
            ))
        return saga_list
    finally:
        db.close()

@app.get("/sagas/{saga_id}", response_model=DetailedSagaView)
def get_saga_details(saga_id: str):
    """Get detailed information about a specific saga"""
    db = SessionLocal()
    try:
        row = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Saga not found")
            
        # Count total events for this saga
        event_count = db.execute(
            saga_events.select().where(saga_events.c.saga_id == saga_id)
        ).rowcount
        
        return DetailedSagaView(
            saga_id=row[1],  # saga_id
            order_id=row[2],  # order_id
            order_status=row[3],  # order_status
            payment_status=row[4],  # payment_status
            delivery_status=row[5],  # delivery_status
            saga_status=row[6] or "started",  # saga_status
            item=row[7],  # item
            quantity=row[8],  # quantity
            price=row[9],  # price
            created_at=row[10],  # created_at
            updated_at=row[11],  # updated_at
            completion_reason=row[12],  # completion_reason
            error_message=row[13],  # error_message
            total_events=event_count
        )
    finally:
        db.close()

@app.get("/sagas/{saga_id}/timeline", response_model=SagaTimeline)
def get_saga_timeline(saga_id: str):
    """Get the complete timeline of events for a saga"""
    db = SessionLocal()
    try:
        # Get saga details
        saga_row = db.execute(sagas.select().where(sagas.c.saga_id == saga_id)).fetchone()
        if saga_row is None:
            raise HTTPException(status_code=404, detail="Saga not found")
            
        # Get all events for this saga
        events_results = db.execute(
            saga_events.select()
            .where(saga_events.c.saga_id == saga_id)
            .order_by(saga_events.c.sequence.asc())
        ).fetchall()
        
        events = []
        for event_row in events_results:
            events.append(SagaEvent(
                id=event_row[0],  # id
                event_type=event_row[2],  # event_type
                service=event_row[3],  # service
                event_data=json.loads(event_row[4]) if event_row[4] else {},  # event_data
                timestamp=event_row[5],  # timestamp
                sequence=event_row[6]  # sequence
            ))
            
        saga_details = DetailedSagaView(
            saga_id=saga_row[1],  # saga_id
            order_id=saga_row[2],  # order_id
            order_status=saga_row[3],  # order_status
            payment_status=saga_row[4],  # payment_status
            delivery_status=saga_row[5],  # delivery_status
            saga_status=saga_row[6] or "started",  # saga_status
            item=saga_row[7],  # item
            quantity=saga_row[8],  # quantity
            price=saga_row[9],  # price
            created_at=saga_row[10],  # created_at
            updated_at=saga_row[11],  # updated_at
            completion_reason=saga_row[12],  # completion_reason
            error_message=saga_row[13],  # error_message
            total_events=len(events)
        )
        
        return SagaTimeline(saga=saga_details, events=events)
    finally:
        db.close()

@app.get("/sagas/{saga_id}/events", response_model=List[SagaEvent])
def get_saga_events(saga_id: str):
    """Get all events for a specific saga"""
    db = SessionLocal()
    try:
        events_results = db.execute(
            saga_events.select()
            .where(saga_events.c.saga_id == saga_id)
            .order_by(saga_events.c.sequence.asc())
        ).fetchall()
        
        events = []
        for event_row in events_results:
            events.append(SagaEvent(
                id=event_row[0],  # id
                event_type=event_row[2],  # event_type
                service=event_row[3],  # service
                event_data=json.loads(event_row[4]) if event_row[4] else {},  # event_data
                timestamp=event_row[5],  # timestamp
                sequence=event_row[6]  # sequence
            ))
        return events
    finally:
        db.close()

@app.get("/stats", response_model=SagaStats)
def get_saga_statistics():
    """Get overall statistics about saga executions"""
    db = SessionLocal()
    try:
        # Count sagas by status
        total_sagas = db.execute(sagas.select()).rowcount
        
        if total_sagas == 0:
            return SagaStats(
                total_sagas=0,
                completed=0,
                failed=0,
                compensated=0,
                in_progress=0,
                started=0,
                success_rate=0.0
            )
        
        completed = db.execute(
            sagas.select().where(sagas.c.saga_status == "completed")
        ).rowcount
        
        failed = db.execute(
            sagas.select().where(sagas.c.saga_status == "failed")
        ).rowcount
        
        compensated = db.execute(
            sagas.select().where(sagas.c.saga_status == "compensated")
        ).rowcount
        
        in_progress = db.execute(
            sagas.select().where(sagas.c.saga_status == "in_progress")
        ).rowcount
        
        started = db.execute(
            sagas.select().where(sagas.c.saga_status == "started")
        ).rowcount
        
        success_rate = (completed / total_sagas) * 100 if total_sagas > 0 else 0.0
        
        return SagaStats(
            total_sagas=total_sagas,
            completed=completed,
            failed=failed,
            compensated=compensated,
            in_progress=in_progress,
            started=started,
            success_rate=round(success_rate, 2)
        )
    finally:
        db.close()

@app.get("/events/recent", response_model=List[SagaEvent])
def get_recent_events(limit: int = Query(20, description="Number of recent events to return")):
    """Get the most recent saga events across all sagas"""
    db = SessionLocal()
    try:
        events_results = db.execute(
            saga_events.select()
            .order_by(saga_events.c.timestamp.desc())
            .limit(limit)
        ).fetchall()
        
        events = []
        for event_row in events_results:
            events.append(SagaEvent(
                id=event_row[0],  # id
                event_type=event_row[2],  # event_type
                service=event_row[3],  # service
                event_data=json.loads(event_row[4]) if event_row[4] else {},  # event_data
                timestamp=event_row[5],  # timestamp
                sequence=event_row[6]  # sequence
            ))
        return events
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)