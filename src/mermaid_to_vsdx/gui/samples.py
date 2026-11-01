"""
Mermaid diagram sample presets for desktop GUI covering all 11 supported diagram types.
"""

SAMPLES = {
    "1. Flowchart - E-Commerce Order & Delivery Pipeline (Flowchart TD)": """graph TD
    A([Customer Places Order]) --> B[Payment Authorization Pending]
    B --> C{Payment Successful?}
    C -->|Yes: Card Charged| D[(Record Order in Database)]
    C -->|No: Insufficient Funds| E[Send Email & SMS Notification]
    E --> F([Cancel Order])
    
    D --> G[Notify Warehouse Logistics]
    G --> H[Generate Invoice & Waybill]
    H --> I[(Shipment Tracking System)]
    I --> J[Dispatched with Courier]
    J --> K([Delivered to Customer])
""",

    "2. Subsystems - Microservices & Data Layer Architecture (Subgraphs LR)": """flowchart LR
    subgraph CLIENT_TIER ["Client Applications & Auth"]
        A[Web Browser Client]
        B[Mobile App iOS & Android]
    end

    subgraph API_GATEWAY ["API Gateway & Security"]
        GW[Reverse Proxy & Firewall]
    end

    subgraph SERVICES ["Core Processing Microservices"]
        S1[User Account Service]
        S2[Payment & Billing Service]
        S3[Notification Service]
    end

    subgraph DATA_LAYER ["Secure Database & Queue Cluster"]
        DB1[(PostgreSQL Primary DB)]
        DB2[(Redis In-Memory Cache)]
        DB3[(Kafka Event Bus)]
    end

    A --> GW
    B --> GW
    GW --> S1
    GW --> S2
    GW --> S3
    S1 --> DB1
    S2 --> DB2
    S3 --> DB3
""",

    "3. Decision Tree - Loan Application & Risk Assessment (Flowchart TD)": """graph TD
    START([Loan Application Received]) --> QUERY[Query Credit Bureau & Score]
    QUERY --> SCORE_CHECK{Score >= 700?}
    
    SCORE_CHECK -->|Yes| INCOME_CHECK{Monthly Income Sufficient?}
    SCORE_CHECK -->|No| REJECT_REASON[High Risk Profile Identified]
    REJECT_REASON --> END_REJECT([Application Rejected])
    
    INCOME_CHECK -->|Yes| APPROVE_LIMIT[Determine Credit Limit & Rate]
    INCOME_CHECK -->|No| GUARANTOR_REQ[Request Guarantor or Collateral]
    
    GUARANTOR_REQ --> GUARANTOR_CHECK{Guarantor Approved?}
    GUARANTOR_CHECK -->|Yes| APPROVE_LIMIT
    GUARANTOR_CHECK -->|No| END_REJECT
    
    APPROVE_LIMIT --> CONTRACT[(Sign Digital Contract)]
    CONTRACT --> DISBURSE([Disburse Loan Funds to Account])
""",

    "4. State Diagram - User Authentication & Session Lifecycle (State Diagram TD)": """stateDiagram-v2
    direction TD
    [*] --> Idle: System Initialized
    Idle --> Authenticating: Login Request
    Authenticating --> Active: Credentials Verified
    Authenticating --> Locked: Failed Attempts (3x)
    Locked --> Idle: Admin Reset
    Active --> Processing: User Selects Task
    Processing --> Active: Task Completed
    Active --> [*]: Secure Logout
""",

    "5. Sequence Diagram - OAuth2 & HealthCheck Protocol (Sequence)": """sequenceDiagram
    autonumber
    actor Alice as Client User
    participant GW as API Gateway
    participant Auth as Auth Service
    Alice->>+GW: POST /login (Credentials)
    GW->>+Auth: Validate Token & MFA
    alt Valid Credentials
        Auth-->>GW: 200 OK (JWT Issued)
        GW-->>Alice: Session Established
    else Invalid Credentials
        Auth-->>-GW: 401 Unauthorized
        GW-->>-Alice: Access Denied
    end
    Note right of Auth: Audit log recorded
""",

    "6. UML Class Diagram - Payment Domain Model (Class Diagram)": """classDiagram
    class PaymentProcessor {
        <<interface>>
        +authorize(amount: Decimal) bool
        +capture(txId: String) Receipt
    }
    class StripeGateway {
        -String apiKey
        +authorize(amount: Decimal) bool
        +capture(txId: String) Receipt
    }
    class Order {
        +UUID orderId
        +Decimal totalAmount
        +checkout()
    }
    PaymentProcessor <|.. StripeGateway : implements
    Order *-- StripeGateway : uses
""",

    "7. ER Diagram - E-Commerce Database Schema (ER Diagram)": """erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    CUSTOMER }|..|{ DELIVERY_ADDRESS : uses
    CUSTOMER {
        uuid customer_id PK
        string full_name
        string email UK
    }
    ORDER {
        uuid order_id PK
        uuid customer_id FK
        datetime created_at
    }
    LINE_ITEM {
        uuid line_id PK
        uuid order_id FK
        int quantity
    }
""",

    "8. Block Diagram - Cloud Infrastructure Grid (Block-Beta)": """block-beta
    columns 3
    lb(["Load Balancer"]):3
    app1["App Server 1"]
    app2["App Server 2"]
    cache(("Redis Cache"))
    db[("Primary Database")]:2
    mq{{"Message Queue"}}
    lb --> app1
    lb --> app2
    app1 --> db
    app2 --> cache
    app2 --> mq
""",

    "9. Mindmap - Enterprise AI Platform Strategy (Mindmap)": """mindmap
  root((Enterprise AI Strategy))
    Data Foundation
      Lakehouse Architecture
      Real-Time Streaming
      Governance & Lineage
    Model Operations
      Fine-Tuning Pipeline
      Vector Search RAG
      Safety Guardrails
    Business Applications
      Customer Copilot
      Automated Analytics
      Document Intelligence
""",

    "10. Timeline - Product Release Roadmap (Timeline)": """timeline
    title Enterprise Platform Release Roadmap
    section Q1 Foundation
        Jan 2026 : Core Engine Architecture : Parser Unification
        Feb 2026 : Headless OPC Compiler : Sugiyama Layout Engine
    section Q2 Expansion
        Apr 2026 : 11 Diagram Types : Multi-Page VSDX
        Jun 2026 : Executive Themes : Visio COM Verification
""",

    "11. Quadrant Chart - Feature Prioritization Matrix (Quadrant)": """quadrantChart
    title Engineering Initiative Prioritization
    x-axis Low Implementation Effort --> High Implementation Effort
    y-axis Low Business Impact --> High Business Impact
    quadrant-1 Strategic Investments
    quadrant-2 Quick Wins
    quadrant-3 Low Priority Fillers
    quadrant-4 Complex Re-Architecture
    Headless VSDX Compiler: [0.28, 0.88]
    Crow's Foot ER Notation: [0.22, 0.76]
    Multi-Page Markdown: [0.42, 0.82]
    Full 3D Stencil Engine: [0.85, 0.68]
    Legacy Format Export: [0.75, 0.25]
    CLI Batch Mode: [0.32, 0.38]
""",

    "12. Pie Chart - Cloud Infrastructure Spend Breakdown (Pie)": """pie showData
    title Cloud Infrastructure Monthly Spend ($K)
    "Compute & Kubernetes" : 45
    "Managed Databases" : 25
    "AI & GPU Inference" : 18
    "Storage & CDN" : 12
""",

    "13. Gantt Chart - System Migration Schedule (Gantt)": """gantt
    title Cloud Migration & Cutover Schedule
    dateFormat YYYY-MM-DD
    section Discovery
        Architecture Audit       :done, des1, 2026-01-01, 5d
        Schema Mapping           :active, des2, after des1, 5d
    section Execution
        Database Replication     :crit, exec1, after des2, 7d
        Service Cutover          :exec2, after exec1, 4d
        Production Go-Live       :milestone, m1, after exec2, 1d
"""
}
