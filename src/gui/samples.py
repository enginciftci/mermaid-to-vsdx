"""
Mermaid diagram sample presets for desktop GUI with various diagram types.
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
"""
}
