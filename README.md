# Customer inquiry assistant

A small command-line assistant that uses Groq tool calling to decide when to query a local service and policy catalogue. Studio facts come from `services.json`; the model is instructed to use only lookup results. Local code screens medical and complaint keywords before any API call, asks for missing treatment details, and blocks booking actions.

## Setup

Python 3.9 or newer is recommended.

```powershell
python -m pip install -r requirements.txt
$env:GROQ_API_KEY = "your-key"
```

The default model is `openai/gpt-oss-120b`. Override it with `GROQ_MODEL` if needed.

## Run

Web form (standard library only):

```powershell
python web_app.py
```

Then open `http://127.0.0.1:8000`. The server binds to localhost. Set `PORT` to use a different local port.
When Groq requests the service-information tool, the terminal shows `Groq requested tool call: lookup_service`, followed by execution and returned service/policy names. The customer message itself is not included in these tool logs.

Each request is also appended to `assistant_traces.jsonl` in this folder. The JSON Lines trace records a request ID, local timestamp (with UTC offset), configured model, route, and tool request/execution events, so you can follow the lifecycle of a request by its ID. It deliberately omits customer messages, tool arguments, and draft replies. The trace file is local and ignored by Git; open it in a text editor or inspect it with `Get-Content assistant_traces.jsonl` in PowerShell.

Interactive:

```powershell
python assistant.py
```

Pass a message directly:

```powershell
python assistant.py "How much is a lash lift and how long does it take?"
```

`lookup_service(query)` reads `services.json` on each call and returns matching service or policy facts. No API key is stored in the project.

Medical or complaint keywords trigger a fixed local reply before Groq is contacted. Booking requests also receive a local response explaining that the assistant cannot make bookings and the studio team will confirm. A broad price question such as “How much does a treatment cost?” asks which treatment the customer means.
