from bs4 import BeautifulSoup

import re
from urllib.parse import urlparse, urljoin, urldefrag

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

unique_pages = set()
word_count = {}
longest_page = {"url" : "", "count" : 0}
subdomains = {}

# Implementation required.
def extract_next_links(url, resp):

    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    if resp.status != 200:
        return []

    if not resp.raw_response or not resp.raw_response.content:
        return []

    if len(resp.raw_response.content) > 5 * 1024 *1024:
        return []
    
    # if it's PDF, image, or random binary data, ignore it
    content_type = resp.raw_response.headers.get("content-type", "")
    if not content_type.startswith("text/html"):
        return []
    
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    urls = []

    # url: the URL that was used to get the page
    unique_pages.add(urldefrag(url).url)
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if href is None:
            continue
        
        new_url = urldefrag(urljoin(url, href)).url
        urls.append(new_url)

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    
    tokens = re.split(r"\W+", text.lower())
    tokens_list = [t for t in tokens if t]
    tokens_not_urls = [t for t in tokens_list if not any(t.startswith(word) for word in ["http", "https", "www", "uci", "edu", "html", "htm"])]
    tokens_min = [t for t in tokens_not_urls if len(t) > 1]
    tokens_not_numeric = [t for t in tokens_min if not t.isnumeric()]

    if len(tokens_not_numeric) < 50:
        return []

    if len(tokens_not_numeric) > longest_page["count"]:
        longest_page["url"] = url
        longest_page["count"] = len(tokens_not_numeric)

    for token in tokens_not_numeric:
        word_count[token] = word_count.get(token, 0) + 1

    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc not in subdomains:
        subdomains[netloc] = set()
    subdomains[netloc].add(url)

    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    return urls

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        if not any(parsed.netloc.endswith(domain) for domain in [".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu"]):
            return False

        # Trap 1: Long URLs
        if len(url) > 200:
            return False
        
        # Trap 2: Repeating directories in path
        if re.match(r"^.*?(/.+?/).*?\1.*$|^.*?/(.+?/)\2.*$", parsed.path):
            return False

        # Trap 3: Calendar/Date Trap: Catches things like /a/b/a/b/a
        if re.search(r"/(19|20)\d{2}-[0-1]\d", parsed.path):
            return False

        # Trap 4: Too many query parameters (e.g ?a=1&b=2&c=3...)
        if url.count('?') > 0 and url.count('&') > 3:
            return False

        # Trap 5: .pdf is hiding in the query parameters
        if "do=export_pdf" in parsed.query.lower():
            return False
        
        # Trap 6: DokuWiki infinite index and action
        if "doku.php" in parsed.path.lower() and parsed.query:
            return False
        
        # Traps: Social sharing links
        if "share=" in parsed.query.lower():
            return False
        
        # Trap: Infinite Calendars and iCal exports
        if "ical=" in parsed.query.lower():
            return False
        
        # Trap: Event Calendar paths (very common on ICS WordPress sites)
        if "/events/" in parsed.path.lower() or "/event/" in parsed.path.lower():
            return False

        # Trap: Blog and News pagination loops
        if "/page/" in parsed.path.lower():
            return False
            
        # Trap: Apache directory sorting parameters (e.g., ?C=N;O=D)
        # This catches anything trying to sort by Name, Date, Size, etc.
        if "c=" in parsed.query.lower() and "o=" in parsed.query.lower():
            return False
            
        # Trap: Dynamic search pages and filters
        if "search=" in parsed.query.lower() or "keywords=" in parsed.query.lower():
            return False

        # Trap: Common raw data and code directories in faculty/student spaces
        if "/~" in parsed.path.lower():
            # If it's a personal directory, block common non-webpage folders
            if re.search(r'/(?:code|src|data|dataset|datasets|bin|patch|releases)/', parsed.path.lower()):
                return False
        
        # Trap: Faculty publication, papers, and citation directories
        # Matches paths like /pub/, /pubs/, /papers/, or files like publications.html
        if re.search(r'/(?:pub|pubs|publications|papers|research-papers)(?:/|\.html?$)', parsed.path.lower()):
            return False
        
        # Trap: Auto-generated HTML slide decks (e.g., sld001.htm, slide01.html)
        if re.search(r'/(?:sld|slide)\d+\.html?$', parsed.path.lower()):
            return False
        
        # Trap: General Presentation folders (like WScacchi's massive archive)
        if "presentations" in parsed.path.lower():
            return False
        
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise
