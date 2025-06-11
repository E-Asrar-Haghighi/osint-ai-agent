# OSINT AI Agent

This project is a demonstration of an OSINT (Open Source Intelligence) AI Agent. The system is designed to process intelligence queries through an automated, multi-agent pipeline, performing strategic data retrieval and synthesizing the findings into a comprehensive investigative report.

The core of the system is built using **LangGraph** for agent orchestration, a **React** frontend for user interaction, and a specialized multi-LLM architecture to handle distinct tasks within the intelligence workflow. This project prioritizes factual accuracy, robust error handling, and the ability to safely manage ambiguous or conflated data—key requirements for any real-world intelligence tool.

## Architecture Diagram

The system implements a two-phase agentic workflow: an **Investigation Loop** for data gathering and a **Reporting & Verification Flow** for synthesis and quality control.



## Architecture Overview & Design Rationale

The system employs a multi-agent pipeline orchestrated by LangGraph, with each agent using a specialized LLM best suited for its task.

1.  **Orchestration Agent (`Claude 3.5 Sonnet`):** A fast and cost-effective model that parses the initial query and strategically selects the next best tool to use from a diverse toolkit based on the ongoing analysis.

2.  **Pivot Agent (`GPT-4o`):** A powerful analytical model that reviews all collected data, synthesizes findings, identifies information gaps, and generates new, intelligent follow-up questions to guide the investigation.

3.  **Cleaner Agent (`Gemini 1.5 Pro`):** This agent specializes in **entity resolution**—a critical OSINT task. It analyzes all raw data to detect and separate potentially conflated identities, structuring the verified facts into distinct profiles with confidence scores. This is the primary defense against hallucination.

4.  **Writer Agent (`Gemini 1.5 Pro`):** Takes the structured, de-conflicted data from the Cleaner and drafts a concise, fact-based intelligence brief. It is instructed to clearly report on any ambiguity or identity conflation found by the Cleaner.

5.  **Judge Agent (`Claude 3 Opus`):** The final, mandatory quality gate. This highly accurate model acts as an adversarial "Red Team," meticulously comparing the drafted report against the source facts. It is given extremely strict instructions to reject any report containing speculation or statements not directly supported by the evidence, ensuring the final output is trustworthy.

### The "Hybrid Tool" Strategy (Mock vs. Real)

Given the 36-hour time constraint, a strategic "Hybrid Tool" approach was implemented to meet all architectural requirements without getting bogged down in multiple, time-consuming API integrations.

*   **Real Tool:** The agent uses one **real, high-quality tool—Tavily for advanced web search**—to provide the factual grounding for its reports. This ensures the final output is based on accurate, real-world data.
*   **Mock Tools:** To prove the orchestrator's ability to manage a diverse toolkit, several **"safe" mock tools** representing social media, academic, and company database searches were implemented. These mocks print a message to the log to prove they were called, but return no data. This prevents fake data from contaminating the report while still demonstrating a fully functional, multi-source retrieval architecture.

## Core Technologies

*   **Backend Framework**: Python, FastAPI, LangGraph
*   **Frontend Framework**: React, TypeScript, Vite
*   **LLM Integrations**: Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, Claude 3 Opus
*   **Data Retrieval**: Tavily AI
*   **Key Python Libraries**: `langchain`, `fastapi`, `tavily-python`, `uvicorn`
*   **Key Frontend Libraries**: `react`, `react-markdown`

---

## Setup and Running the Project

### Prerequisites

Before you begin, ensure you have the following:
*   Python 3.10+
*   Node.js 18+ and npm
*   API keys for:
    *   OpenAI
    *   Anthropic (for Claude)
    *   Google AI (for Gemini)
    *   Tavily AI

### 1. Backend Setup

First, set up and run the Python backend server.

```bash
# 1. Navigate to the api directory
cd api

# 2. Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install the required dependencies
pip install -r requirements.txt

# 4. Create the environment file
# Create a new file named .env in the api/ directory and paste the following,
# replacing "your_key_here" with your actual API keys.
```

**`api/.env` file:**
```env
OPENAI_API_KEY="your_key_here"
ANTHROPIC_API_KEY="your_key_here"
GOOGLE_API_KEY="your_key_here"
TAVILY_API_KEY="your_key_here"
```

```bash
# 5. Run the backend server
uvicorn app.main:app --reload
```
The backend will now be running on `http://localhost:8000`.

### 2. Frontend Setup

Next, set up and run the React frontend in a **separate terminal**.

```bash
# 1. Navigate to the frontend directory from the project root
cd frontend

# 2. Install the required dependencies
npm install

# 3. Run the frontend development server
npm run dev
```
Your browser should automatically open to the application, typically at `http://localhost:5174`.

---

## How to Use

The application is designed to fulfill the primary test case of the assignment.

1.  Open your browser to the application's URL.
2.  In the input field, type the investigation target: **The name that you want to investigate**.
3.  Click the **"Start Investigation"** button.
4.  Observe the **"Investigation Log"** on the UI. It will update in real-time, showing the internal monologue and actions of each agent in the pipeline.
5.  Once the investigation is complete, the final, formatted intelligence report will appear. Note that the report may be a "FAILED QUALITY CHECK" message from the Judge agent—this is a successful demonstration of the system's internal quality controls at work.

## Fulfilling the Evaluation Criteria

This project meets the core requirements of the technical challenge:

| Requirement                  | Implementation                                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| **Framework**                | The system is built entirely on **LangGraph** with a stateful, event-driven architecture.                        |
| **Multi-Model Implementation** | Uses **4 distinct LLMs** (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, Claude Opus) for their specialized roles.       |
| **Agent Pipeline**             | Implements the full Query Analysis -> Orchestrate -> Pivot -> Synthesize -> Judge pipeline.                    |
| **Multi-Source Retrieval**   | The orchestrator successfully calls a diverse set of tools (real and mock) to prove the architecture works. |
| **Dynamic Routing**            | The graph uses a conditional edge (`should_continue`) to intelligently loop or end the investigation. |
| **React Frontend**             | A functional UI allows for query submission, real-time status tracking, and final report visualization.      |
| **Elaborate Prompts**          | The `api/app/prompts.py` file contains detailed, role-specific prompts designed to enforce accuracy.    |
| **Test Case Fulfillment**      | The application is built and tested to successfully process the "Ali Khaledi Nasab" investigation, demonstrating advanced features like entity resolution and AI-powered quality control.             |
