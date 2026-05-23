import sys
import os

# Add the parent directory to the path so we can import config and agents
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents.paper_searcher import search_papers

def my_callback(msg):
    print(msg)

if __name__ == "__main__":
    print("Testing search_papers...")
    papers = search_papers(
        query="NTT algorithm hardware optimization",
        desired_count=10,
        progress_callback=my_callback
    )
    
    print("\n--- Results ---")
    print(f"Total papers found: {len(papers)}")
    sources = {}
    for p in papers:
        src = p.get("source", "Unknown")
        sources[src] = sources.get(src, 0) + 1
        
    for src, count in sources.items():
        print(f"{src}: {count} papers")
