import os
import asyncio
from moss import MossClient, DocumentInfo, QueryOptions
from dotenv import load_dotenv
load_dotenv()




client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))
index_name = "demo-customer_faqs"

async def main():
    #===========================load the index============================
    await client.load_index(index_name)
    print("Index loaded successfully.")

    #===========================query the index============================
    results = await client.query(
        index_name, 
        "How do I return a damaged product?", 
        QueryOptions(
            top_k=3, 
            alpha=0.6,
            filter={"field": "category", "condition": {"$eq": "returns"}}))
    
    print(f"  ID: {results.docs[0].id}")
    print(f"  Text: {results.docs[0].text}")
    print(f"  Score: {results.docs[0].score}")
    print(f"  Metadata: {results.docs[0].metadata}")
    #=============================================================================

asyncio.run(main())