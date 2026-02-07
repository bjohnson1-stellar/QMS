@echo off
REM SIS Embedding Queue Processor
REM Run this via Windows Task Scheduler or manually
REM
REM Prerequisites:
REM   - LM Studio running with nomic-embed-text model loaded
REM   - Python environment with chromadb, openai packages
REM
REM Schedule with Task Scheduler:
REM   Program: D:\QC-DR\scripts\process_embeddings.bat
REM   Start in: D:\QC-DR
REM   Trigger: When LM Studio is running, or Daily at specific time

cd /d D:\QC-DR

echo [%date% %time%] Starting embedding queue processing...

REM Check if LM Studio is responding
curl -s http://127.0.0.1:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] LM Studio not available - skipping
    exit /b 0
)

REM Process the queue
python embed_queue.py process

echo [%date% %time%] Embedding processing complete
