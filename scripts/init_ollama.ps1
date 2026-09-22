Write-Host "Pulling models into Ollama container..." -ForegroundColor Cyan

docker exec ollama ollama pull qwen2.5-coder:7b
docker exec ollama ollama pull qwen2.5vl:7b
docker exec ollama ollama pull nomic-embed-text

Write-Host "Done. Listing models:" -ForegroundColor Green
docker exec ollama ollama list
