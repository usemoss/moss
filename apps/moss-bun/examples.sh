#!/bin/bash
# Moss Bun API Examples

BASE_URL="http://localhost:3000"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌿 Moss Bun API Examples${NC}\n"

# 1. Health Check
echo -e "${GREEN}1. Health Check${NC}"
curl -s "$BASE_URL/health" | jq .
echo ""

# 2. Server Status
echo -e "${GREEN}2. Server Status${NC}"
curl -s "$BASE_URL/status" | jq .
echo ""

# 3. Initialize Index
echo -e "${GREEN}3. Initialize Index${NC}"
curl -s -X POST "$BASE_URL/api/initialize" \
  -H "Content-Type: application/json" \
  -d '{
    "indexName": "example-index",
    "documents": [
      {
        "id": "1",
        "text": "Moss is a semantic search runtime for AI agents"
      },
      {
        "id": "2",
        "text": "Bun is a JavaScript runtime and toolkit"
      },
      {
        "id": "3",
        "text": "Semantic search finds documents by meaning, not keywords"
      },
      {
        "id": "4",
        "text": "LLMs can power intelligent search and retrieval"
      },
      {
        "id": "5",
        "text": "RAG combines retrieval with language generation"
      }
    ]
  }' | jq .
echo ""

# 4. List Loaded Indexes
echo -e "${GREEN}4. List Loaded Indexes${NC}"
curl -s "$BASE_URL/api/indexes" | jq .
echo ""

# 5. Single Search
echo -e "${GREEN}5. Single Search${NC}"
curl -s -X POST "$BASE_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is semantic search?",
    "topK": 3,
    "indexName": "example-index"
  }' | jq .
echo ""

# 6. Batch Search
echo -e "${GREEN}6. Batch Search${NC}"
curl -s -X POST "$BASE_URL/api/search-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      "What is Moss?",
      "Tell me about Bun",
      "Explain RAG"
    ],
    "topK": 2,
    "indexName": "example-index"
  }' | jq .
echo ""

# 7. Add Documents
echo -e "${GREEN}7. Add Documents${NC}"
curl -s -X POST "$BASE_URL/api/docs/add" \
  -H "Content-Type: application/json" \
  -d '{
    "indexName": "example-index",
    "documents": [
      {
        "id": "6",
        "text": "Vector embeddings convert text into semantic representations"
      }
    ]
  }' | jq .
echo ""

# 8. Get Index Info
echo -e "${GREEN}8. Get Index Info${NC}"
curl -s "$BASE_URL/api/index/example-index" | jq .
echo ""

# 9. Get Specific Document
echo -e "${GREEN}9. Get Specific Document${NC}"
curl -s "$BASE_URL/api/docs/example-index/1" | jq .
echo ""

# 10. Performance Benchmark
echo -e "${GREEN}10. Performance Benchmark${NC}"
echo "Running 5 sequential searches..."
for i in {1..5}; do
  echo "Query $i..."
  curl -s -X POST "$BASE_URL/api/search" \
    -H "Content-Type: application/json" \
    -d "{
      \"query\": \"search query $i\",
      \"topK\": 2,
      \"indexName\": \"example-index\"
    }" | jq '.timeTakenMs'
done

echo -e "\n${BLUE}✅ Examples complete!${NC}"
