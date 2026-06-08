import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from typing import Dict, Any

def scrape_url(url: str) -> Dict[str, Any]:
    """
    Scrapes the content of a web page and extracts relevant information
    such as the title, main body text, and meta description.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    result = {
        "url": url,
        "title": "",
        "content": "",
        "meta_description": "",
        "domain": "",
        "error": None
    }
    
    try:
        # Parse domain for reference
        parsed_url = urllib.parse.urlparse(url)
        result["domain"] = parsed_url.netloc.replace("www.", "")
        
        # Fetch web page
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, "lxml")
        
        # Extract title
        title_tag = soup.find("title")
        result["title"] = title_tag.string.strip() if title_tag else ""
        
        # Extract meta description
        meta_desc = (
            soup.find("meta", attrs={"name": "description"}) or
            soup.find("meta", attrs={"property": "og:description"})
        )
        if meta_desc:
            result["meta_description"] = meta_desc.get("content", "").strip()
            
        # Remove unwanted tags
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            element.decompose()
            
        # Attempt to extract article/body content
        # Standard news sites structure articles in specific tags or classes
        article_body = None
        for tag in ["article", "main", ".article-body", ".post-content", ".entry-content"]:
            if tag.startswith("."):
                article_body = soup.select_one(tag)
            else:
                article_body = soup.find(tag)
            if article_body:
                break
                
        if not article_body:
            article_body = soup.body
            
        if article_body:
            # Join paragraphs or text segments with double newlines
            paragraphs = [p.get_text().strip() for p in article_body.find_all(["p", "h1", "h2", "h3", "h4", "li"])]
            content = "\n\n".join([p for p in paragraphs if p])
            # Clean up double spacing and multi-newlines
            content = re.sub(r'\n{3,}', '\n\n', content)
            result["content"] = content
        else:
            result["content"] = soup.get_text(separator="\n\n").strip()
            
        # Trim to reasonable length to prevent massive token inflation (e.g. max ~15000 chars)
        if len(result["content"]) > 15000:
            result["content"] = result["content"][:15000] + "\n...[Content truncated due to length]..."
            
    except Exception as e:
        result["error"] = str(e)
        result["content"] = f"Error fetching article content: {str(e)}"
        
    return result
