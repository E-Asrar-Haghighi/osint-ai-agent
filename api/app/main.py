from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import uuid
import json
import traceback
import sys

from .graph import app as graph_app # The compiled LangGraph app

app = FastAPI()

# In-memory store for stream events. In a real-world scenario,
# you might use Redis or another message queue.
STREAMS = {}

# CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Thread-ID"], # Expose custom header
)

async def run_investigation_and_store_results(thread_id: str, initial_state: dict, config: dict):
    """Runs the graph and stores each chunk in the in-memory STREAMS dict."""
    STREAMS[thread_id] = []
    final_report = ""
    try:
        print("[DEBUG] Starting investigation with initial state:", json.dumps(initial_state, indent=2))
        
        # Set a higher recursion limit for this investigation
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(2000)  # Set a higher limit
        
        try:
            async for chunk in graph_app.astream(initial_state, config=config, stream_mode="values"):
                log_entry = chunk["log"][-1]
                print(f"[DEBUG] Investigation chunk: {log_entry}")
                print(f"[DEBUG] Current state: {json.dumps(chunk, indent=2)}")
                STREAMS[thread_id].append({"data": json.dumps({"log": log_entry})})
                final_report = chunk.get("final_report", "")
        finally:
            # Restore the original recursion limit
            sys.setrecursionlimit(old_limit)
            
        # After the loop, add the final report
        if not final_report:
            final_report = "ERROR: No final report generated."
            print("[ERROR] No final report generated by investigation.")
            print("[DEBUG] Final state:", json.dumps(chunk, indent=2))
        else:
            print("[DEBUG] Final report successfully generated.")
        STREAMS[thread_id].append({"data": json.dumps({"report": final_report})})
    except Exception as e:
        error_message = f"ERROR: An error occurred during investigation: {e}\n{traceback.format_exc()}"
        print(error_message)
        STREAMS[thread_id].append({"data": json.dumps({"log": error_message})})
        # Always send a final report, even if error
        STREAMS[thread_id].append({"data": json.dumps({"report": "ERROR: Investigation failed. See logs for details."})})
    finally:
        # Add a special event to signal the end of the stream
        print("[DEBUG] Investigation stream ended.")
        STREAMS[thread_id].append({"event": "end"})


@app.post("/investigate")
async def investigate(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    query = data.get("query")
    
    if not query:
        return JSONResponse(status_code=400, content={"message": "Query is required."})

    thread_id = str(uuid.uuid4())
    
    # The 'configurable' key is at the top level. This is what the checkpointer uses.
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    # We start with an empty follow_up_queries list. The orchestrator's first
    # job is to generate the first real query from the main `query`.
    initial_state = {
        "query": query,
        "entities": [],
        "plan": "",
        "retrieved_data": [],
        "log": [f"START: Beginning investigation for query: {query}"],
        "analysis": "No analysis yet.",
        "follow_up_queries": [], # Start empty
        "retrieval_count": 0,
        "cleaned_data": {}, # Ensure this matches the type in types.py
        "final_report": ""
    }
    
    # Run the long-running graph in the background
    background_tasks.add_task(run_investigation_and_store_results, thread_id, initial_state, config)
    
    # Immediately return the thread_id so the client can connect to the stream
    return JSONResponse(
        content={"message": "Investigation started.", "thread_id": thread_id},
        headers={"X-Thread-ID": thread_id}
    )

@app.get("/stream/{thread_id}")
async def stream_events(thread_id: str):
    async def event_generator():
        last_sent_index = 0
        while True:
            # Check for new events
            if thread_id in STREAMS and len(STREAMS[thread_id]) > last_sent_index:
                for i in range(last_sent_index, len(STREAMS[thread_id])):
                    event = STREAMS[thread_id][i]
                    if event.get("event") == "end":
                        yield {"event": "close"} # SSE close signal
                        del STREAMS[thread_id] # Clean up
                        return
                    yield event
                last_sent_index = len(STREAMS[thread_id])
            
            # If the stream is closed from the other end, exit
            if thread_id not in STREAMS:
                return

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
