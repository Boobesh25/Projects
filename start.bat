@echo off
echo ============================================
echo   RAG Reranker - Starting All Services
echo ============================================

echo.
echo [1/4] Waiting for Docker...
:wait_docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 3 /nobreak >nul
    goto wait_docker
)

echo [2/4] Starting Docker containers (Postgres, Qdrant, Redis)...
cd /d E:\Learnings\projects\Rag_Reranker
docker-compose up -d

echo [3/4] Waiting for PostgreSQL to be ready...
timeout /t 8 /nobreak >nul

echo [4/4] Starting MCP Server (port 8001) and API (port 8000)...
echo.
start "MCP Web Search Server" cmd /k "e:\Learnings\projects\Autogen_chat\venv\Scripts\python.exe run_mcp_server.py"
timeout /t 3 /nobreak >nul
echo.
echo ============================================
echo   MCP Server: http://localhost:8001
echo   API:        http://localhost:8000
echo   Frontend:   Run separately: streamlit run src/frontend/app.py
echo ============================================
echo.
e:\Learnings\projects\Autogen_chat\venv\Scripts\python.exe run_api.py
