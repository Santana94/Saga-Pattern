# 🏗️ FastAPI Microservices with Choreographed Saga Pattern

A distributed e-commerce system implementing the **Choreographed Saga Pattern** using FastAPI, Kafka, and PostgreSQL. This project demonstrates how to handle distributed transactions across multiple microservices without a central coordinator.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Services](#services)
- [Choreographed Saga Pattern](#choreographed-saga-pattern)
- [System Flow](#system-flow)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KAFKA EVENT BUS                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │   orders    │ │  payments   │ │delivery_evts│ │   compensations     │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
           │              │              │                    │
           ▼              ▼              ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Order Service  │ │ Payment Service │ │Delivery Service │ │   Saga View     │
│   Port: 8000    │ │   Port: 8001    │ │   Port: 8002    │ │   Port: 8005    │
│                 │ │                 │ │                 │ │                 │
│ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │  order_db   │ │ │ │ payment_db  │ │ │ │delivery_db  │ │ │ │  saga_db    │ │
│ │ Port: 15432 │ │ │ │ Port: 15433 │ │ │ │ Port: 15434 │ │ │ │ Port: 15435 │ │
│ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 🎯 Services

### 1. **Order Service** (Port 8000)
- **Purpose**: Manages order creation and cancellation
- **Database**: PostgreSQL (port 15432)
- **Responsibilities**:
  - Creates new orders
  - Publishes `OrderCreated` events
  - Handles order cancellation (compensation)

### 2. **Payment Service** (Port 8001)
- **Purpose**: Processes payments and refunds
- **Database**: PostgreSQL (port 15433)
- **Responsibilities**:
  - Processes payments for created orders
  - Publishes `PaymentProcessed` or `PaymentFailed` events
  - Handles payment refunds (compensation)

### 3. **Delivery Service** (Port 8002)
- **Purpose**: Schedules deliveries
- **Database**: PostgreSQL (port 15434)
- **Responsibilities**:
  - Schedules deliveries after successful payments
  - Publishes `DeliveryScheduled` or `DeliveryFailed` events
  - Handles delivery cancellation (compensation)

### 4. **Saga View Service** (Port 8005)
- **Purpose**: Provides monitoring and visualization of saga executions
- **Database**: PostgreSQL (port 15435)
- **Responsibilities**:
  - Tracks all saga events across services
  - Provides REST API for saga monitoring
  - Maintains saga state and timeline

## 🔄 Choreographed Saga Pattern

### What is a Choreographed Saga?

A **Choreographed Saga** is a pattern for managing distributed transactions where each service knows what to do and when to do it, without a central coordinator. Services communicate through events and handle their own compensations.

### Key Characteristics:
- ✅ **Decentralized**: No central orchestrator
- ✅ **Event-Driven**: Services communicate via events
- ✅ **Autonomous**: Each service manages its own logic
- ✅ **Resilient**: Automatic compensation on failures

### Saga Flow Diagram

```
┌─────────────┐    OrderCreated     ┌─────────────┐    PaymentProcessed    ┌─────────────┐
│             │ ─────────────────► │             │ ─────────────────────► │             │
│   Order     │                    │   Payment   │                        │  Delivery   │
│  Service    │                    │   Service   │                        │  Service    │
│             │ ◄───────────────── │             │ ◄───────────────────── │             │
└─────────────┘   CancelOrder      └─────────────┘   RefundPayment        └─────────────┘
       │              ▲                    │              ▲                       │
       │              │                    │              │                       │
       ▼              │                    ▼              │                       ▼
┌─────────────┐       │             ┌─────────────┐       │                ┌─────────────┐
│   order_db  │       │             │ payment_db  │       │                │ delivery_db │
└─────────────┘       │             └─────────────┘       │                └─────────────┘
                      │                                   │
                      │              ┌─────────────┐      │
                      └──────────────│ Saga View   │──────┘
                                     │   Service   │
                                     │             │
                                     └─────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  saga_db    │
                                    └─────────────┘
```

## 🔄 System Flow

### Happy Path: Successful Order

```
1. 📝 User creates order
   POST /orders → Order Service

2. 🎯 Order Service
   - Saves order to database
   - Publishes OrderCreated event
   - Generates unique saga_id

3. 💳 Payment Service
   - Receives OrderCreated event
   - Processes payment
   - Publishes PaymentProcessed event

4. 🚚 Delivery Service
   - Receives PaymentProcessed event
   - Schedules delivery
   - Publishes DeliveryScheduled event

5. ✅ Saga Complete
   - All services successful
   - Saga View tracks completion
```

### Compensation Path: Payment Fails

```
1. 📝 User creates order
   POST /orders → Order Service

2. 🎯 Order Service
   - Saves order to database
   - Publishes OrderCreated event

3. ❌ Payment Service
   - Receives OrderCreated event
   - Payment processing fails
   - Publishes PaymentFailed event

4. 🔄 Compensation Triggered
   - Order Service receives PaymentFailed
   - Cancels the order
   - Publishes OrderCancelled event

5. 📊 Saga View
   - Tracks failed saga
   - Marks status as "failed"
```

### Compensation Path: Delivery Fails

```
1-3. Normal flow (Order → Payment successful)

4. ❌ Delivery Service
   - Receives PaymentProcessed event
   - Delivery scheduling fails
   - Publishes DeliveryFailed event
   - Triggers RefundPayment event

5. 🔄 Payment Compensation
   - Payment Service receives RefundPayment
   - Processes refund
   - Publishes PaymentRefunded event

6. 🔄 Order Compensation
   - Order Service receives compensation signal
   - Cancels the order
   - Publishes OrderCancelled event

7. 📊 Saga View
   - Tracks compensated saga
   - Marks status as "compensated"
```

## 📊 Event Types and Topics

### Kafka Topics:
- **`orders`**: Order-related events
- **`payments`**: Payment-related events  
- **`delivery_events`**: Delivery-related events
- **`order_compensations`**: Order compensation events
- **`payment_compensations`**: Payment compensation events
- **`delivery_compensations`**: Delivery compensation events

### Event Types:
```json
// Order Events
{"type": "OrderCreated", "order_id": 1, "saga_id": "uuid", "item": "laptop", "price": 999.99}
{"type": "OrderCancelled", "order_id": 1, "saga_id": "uuid"}

// Payment Events  
{"type": "PaymentProcessed", "order_id": 1, "saga_id": "uuid", "amount": 999.99}
{"type": "PaymentFailed", "order_id": 1, "saga_id": "uuid", "reason": "insufficient_funds"}
{"type": "PaymentRefunded", "order_id": 1, "saga_id": "uuid", "amount": 999.99}

// Delivery Events
{"type": "DeliveryScheduled", "order_id": 1, "saga_id": "uuid"}
{"type": "DeliveryFailed", "order_id": 1, "saga_id": "uuid", "reason": "address_invalid"}
{"type": "DeliveryCancelled", "order_id": 1, "saga_id": "uuid"}

// Compensation Events
{"type": "RefundPayment", "order_id": 1, "saga_id": "uuid", "reason": "delivery_failed"}
{"type": "CancelOrder", "order_id": 1, "saga_id": "uuid", "reason": "payment_failed"}
```

## 🚀 Setup & Installation

### Prerequisites
- Python 3.8+
- Docker & Docker Compose
- Git

### 1. Clone Repository
```bash
git clone <repository-url>
cd FastAPIProject
```

### 2. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start Infrastructure
```bash
# Start databases and Kafka
docker compose up -d kafka order_db payment_db delivery_db saga_db

# Wait for services to be ready
sleep 10
```

### 4. Start Services (Development)

**Option A: Run all in Docker**
```bash
docker compose up -d
```

**Option B: Run locally (for development)**
```bash
# Terminal 1 - Order Service
python -m uvicorn order_service.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 - Payment Service  
python -m uvicorn payment_service.main:app --host 127.0.0.1 --port 8001 --reload

# Terminal 3 - Delivery Service
python -m uvicorn delivery_service.main:app --host 127.0.0.1 --port 8002 --reload

# Terminal 4 - Saga View Service
python -m uvicorn saga_view.main:app --host 127.0.0.1 --port 8005 --reload
```

## 📱 Usage

### Create an Order
```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "item": "laptop",
    "quantity": 1,
    "price": 999.99
  }'
```

### Monitor Saga Progress
```bash
# Get all sagas
curl "http://localhost:8005/sagas"

# Get saga details
curl "http://localhost:8005/sagas/{saga_id}"

# Get saga timeline
curl "http://localhost:8005/sagas/{saga_id}/timeline"

# Get saga statistics
curl "http://localhost:8005/stats"

# Get recent events
curl "http://localhost:8005/events/recent"
```

### Health Checks
```bash
curl "http://localhost:8000/"  # Order Service
curl "http://localhost:8001/"  # Payment Service  
curl "http://localhost:8002/"  # Delivery Service
curl "http://localhost:8005/"  # Saga View Service
```

## 📚 API Documentation

### Order Service (Port 8000)
- `POST /orders` - Create a new order
- `GET /` - Health check

### Payment Service (Port 8001)
- `GET /` - Health check

### Delivery Service (Port 8002)
- `GET /` - Health check

### Saga View Service (Port 8005)
- `GET /sagas` - List all sagas (with filtering)
- `GET /sagas/{saga_id}` - Get saga details
- `GET /sagas/{saga_id}/timeline` - Get saga event timeline
- `GET /sagas/{saga_id}/events` - Get saga events
- `GET /stats` - Get saga statistics
- `GET /events/recent` - Get recent events across all sagas
- `GET /` - Health check

Visit `http://localhost:8005/docs` for interactive Swagger documentation.

## 📊 Monitoring

### Saga View Dashboard

The Saga View service provides comprehensive monitoring:

```
📊 Saga Statistics:
- Total Sagas: 150
- Completed: 120 (80%)
- Failed: 20 (13.3%)
- Compensated: 8 (5.3%)
- In Progress: 2 (1.3%)
- Success Rate: 80%

📈 Recent Activity:
- OrderCreated (Order Service) - 2 min ago
- PaymentProcessed (Payment Service) - 1 min ago  
- DeliveryScheduled (Delivery Service) - 30 sec ago
```

### Logging

All services provide detailed logging:
- 🎯 Service startup and configuration
- 📨 Message processing with Kafka details
- 💓 Heartbeat logs every 30 seconds
- ❌ Error handling with stack traces
- 🔄 Compensation flows

### Key Metrics to Monitor:
- **Saga Success Rate**: % of sagas that complete successfully
- **Average Processing Time**: Time from order creation to completion
- **Compensation Rate**: % of sagas requiring compensation
- **Service Health**: Individual service status and response times

## 🔧 Troubleshooting

### Common Issues

#### 1. Kafka Connection Errors
```
❌ KafkaConnectionError: Kafka not ready after several retries
```
**Solution**: Ensure Kafka is running and accessible
```bash
docker compose logs kafka
docker compose restart kafka
```

#### 2. Database Connection Errors
```
❌ Could not translate host name "order_db" to address
```
**Solution**: Check database containers and environment variables
```bash
docker compose ps
docker compose logs order_db
```

#### 3. Port Already in Use
```
❌ [Errno 48] Address already in use
```
**Solution**: Check for running processes or change ports
```bash
lsof -i :8000
# Kill process or use different port
```

#### 4. No Logs from Consumers
**Symptoms**: Services start but don't process messages
**Solution**: Check startup logs for consumer initialization
```bash
# Look for these logs:
✅ Consumer started successfully
💓 Heartbeat logs every 30 seconds  
📨 Message processing logs
```

### Development Tips

#### 1. Running Services Locally
- Use environment variables for configuration
- Databases: `localhost:15432-15435`
- Kafka: `localhost:9092`

#### 2. Debugging Event Flow
- Monitor Saga View for event timeline
- Check individual service logs
- Use Kafka tools to inspect topics

#### 3. Testing Compensations
- Introduce artificial failures in services
- Monitor compensation flow in logs
- Verify saga status changes in Saga View

### Environment Variables

For local development, you can skip Kafka:
```bash
export SKIP_KAFKA=true
```

This allows testing individual services without Kafka dependency.

## 🏗️ Architecture Benefits

### Advantages of Choreographed Saga:
1. **Decentralization**: No single point of failure
2. **Autonomy**: Services own their logic and data
3. **Scalability**: Independent service scaling
4. **Loose Coupling**: Services communicate via events
5. **Observability**: Complete event audit trail

### Trade-offs:
1. **Complexity**: More complex than centralized orchestration
2. **Debugging**: Distributed flow can be harder to trace
3. **Event Management**: Requires careful event design
4. **Eventual Consistency**: Data consistency is eventual, not immediate

## 🔄 Future Enhancements

- [ ] Add circuit breakers for resilience
- [ ] Implement event sourcing for complete audit trail  
- [ ] Add metrics collection (Prometheus/Grafana)
- [ ] Implement distributed tracing (Jaeger)
- [ ] Add automated testing for saga flows
- [ ] Implement event replay functionality
- [ ] Add API rate limiting and authentication
- [ ] Create web UI for saga monitoring
